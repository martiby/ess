import logging
import subprocess
import time
from copy import deepcopy
from datetime import datetime

import version
from api_request import ApiRequest
from blackbox import Blackbox
from config import config
from fsm import FSM
from ha_report import HaReport
from multiplus2 import MultiPlus2
from timer import Timer
from trace import Trace
from bms_us2000 import US2000
from utils import *
from web import AppWeb

# from bms_dummy import BMS_DUMMY

"""
ESS Application
"""

class App(FSM):
    MAX_ERROR_ACKS_PER_DAY = 5
    ERROR_ACK_INTERVAL = 10
    FEED_STUCK_POWER = 300  # [W] feed set value from which the multiplus must deliver power
    FEED_STUCK_INV_P = 50  # [W] inverter power below this value = no feed
    FEED_STUCK_TIME = 20  # [s] no feed for this time -> multiplus restart (sleep / wakeup)
    FEED_STUCK_MAX_RESTARTS = 3  # max multiplus restarts per hour
    MP2_RESTART_SLEEP_TIME = 15  # [s] multiplus sleep time at restart

    def __init__(self):
        super().__init__('init')
        self.www_path = config['www_path']
        self.log = logging.getLogger('app')
        self.web = AppWeb(self)
        self.trace = Trace()
        self.config = config
        self.cycle_time = config.get('cycle_time', 0.75)  # [s] mainloop cycle time
        self.gain = config.get('regulator_gain', 0.12)  # regulator gain, power up (more charge / feed)
        self.gain_down = config.get('regulator_gain_down', self.gain)  # regulator gain, power down (faster)
        self.feed_target = config.get('feed_grid_target', (-5, 0))  # [W] (min, max) grid power target while feeding
        self.meterhub = ApiRequest(config['meterhub_address'], timeout=0.5, lifetime=10, log_name='meterhub')
        self.ha = HaReport(config.get('ha_webhook_url'), interval=config.get('ha_interval', 10), timeout=1)  # Home Assistant, own thread

        if 'bms_us2000' in config:
            self.bms = US2000(**self.config['bms_us2000'])  # pass config to BMS class
        # elif 'bms_seplos' in config:
        #     self.bms = SEPLOS(**self.config['bms_seplos'])  # pass config to BMS class
        else:
            self.log.exception("undefined BMS")
            self.bms = None

        self.multiplus = MultiPlus2(config['victron_mk3_port'])
        self.blackbox = Blackbox(size=config['blackbox_size'],
                                 path=config['log_path'],
                                 csv_config=config.get('csv_log', None))

        self.mode = 'auto'  # Operation mode: 'off', 'auto', 'manual'
        self.set_p = 0  # power set value
        self.reg_p = 0  # regulator power for auto_charge / auto_feed, reset at state entry
        self.setting = 0  # 0, 1, ... Index to usersettings from config/ui

        self.ui_command = None  # commands from UI sent with polling, manual commands
        self.feed_throttle = False  # limit max feed at high continous feed
        self.error_ack_count = 0
        self.error_ack_date = datetime.now().date()
        self.error_ack_timer = Timer()

        # values from MeterHub and BMS
        self.grid_p = 0
        self.home_p = 0
        self.home_all_p = 0
        self.car_p = 0
        self.pv_p = 0
        self.meter_online = True  # smartmeter values (home_p) available

        self.charge_start_timer = Timer()
        self.feed_start_timer = Timer()
        self.feed_throttle_timer = Timer()
        self.state_timer = Timer()
        self.mp2_wait_timer = Timer()  # max wait for multiplus 'on' in auto_charge / auto_feed
        self.feed_stuck_timer = Timer()  # watchdog: multiplus on, high feed set value, but no power
        self.mp2_restart_timer = Timer()  # multiplus restart (sleep / wakeup) in progress
        self.mp2_restart_times = []  # time.time() of restarts in the last hour
        self.mp2_restart_limit_logged = False


    def get_setting(self, name):
        """
        Give a setting depending on the option used or default
        :param name: key
        :return: value
        """
        if name in self.config['setting'][self.setting]:
            return self.config['setting'][self.setting][name]  # use custom setting
        else:
            return self.config['setting'][0][name]  # default or fallback to default

    def reset_daily_error_ack_count(self):
        today = datetime.now().date()
        if today != self.error_ack_date:
            self.error_ack_count = 0
            self.error_ack_date = today
            self.log.info("daily automatic error reset count cleared")

    def start(self):
        """
        Application mainloop
        """
        self.log.info('start ess {}'.format(version.__version__))

        while True:
            t_begin = time.perf_counter()  # cycle start time
            self.reset_daily_error_ack_count()

            # === meterhub ===================================================   ~ 15ms

            self.meterhub.read(
                post={'bat_info': self.get_info_text(), 'bat_soc': self.bms.soc})
            self.log.debug("meterhub {}".format(self.meterhub.data))

            # === bms ===================================================   ~ 0ms (Thread)

            self.bms.update()
            self.log.debug("bms {}".format(self.bms.get_state()))

            # ================================================================

            if self._fsm_state not in ('error', 'init'):
                self.fsm_switch()
            self.update_in()
            self.handle_power_command()  # shutdown / reboot, also in error state
            self.run_fsm()
            self.trace.push(deepcopy(self.get_state()))

            # === Multiplus ===================================================

            self.multiplus.command(self.set_p)
            time.sleep(0.075)
            self.multiplus.update(pause_time=0.075)
            self.log.debug("multiplus {}".format(self.multiplus.data))

            # === Blackbox ===================================================

            self.blackbox.push(self.get_state(bms_detail=True))

            # ================================================================

            t_end = time.perf_counter()
            while time.perf_counter() < t_begin + self.cycle_time:
                time.sleep(0.01)

            # typical ~ 680ms (synced to cycle_time)

            # print("loop {:.3f}s/{:.3f}s ".format(t_end - t_begin, time.perf_counter() - t_begin))

            # =================================================================
            # === Update Battery SOC and power to HA ==========================
            try:
                power = int(self.multiplus.data['inv_p'] or 0) * -1
            except:
                power = 0
            self.ha.update(int(self.bms.soc or 0), power)  # non blocking, sent by HaReport thread

            # =================================================================


    def update_in(self):
        """
        Acquire all incoming data
        """
        self.grid_p = dictget(self.meterhub.data, 'grid_p')
        self.car_p = dictget(self.meterhub.data, 'car_p')
        self.pv_p = dictget(self.meterhub.data, 'pv_p')
        self.home_all_p = dictget(self.meterhub.data, 'home_all_p')

        # if self.home_all_p and self.car_p:
        #    self.home_p = self.home_all_p - self.car_p
        if self.home_all_p is not None:
            self.home_p = self.home_all_p
        else:
            self.home_p = None

        if self.home_p is None and self.meter_online:
            self.meter_online = False
            self.log.warning("smartmeter data missing, no auto charge/feed")
        elif self.home_p is not None and not self.meter_online:
            self.meter_online = True
            self.log.info("smartmeter data available again")


    def fsm_switch(self):
        """
        Auto state change by events
        """
        if self.bms.voltage and self.bms.voltage > self.config['udc_max']:
            self.log.error("error max voltage at bms {}".format(self.bms.get_state()))
            self.set_fsm_state('error')
        elif self.bms.temperature and self.bms.temperature > self.config['t_max']:
            self.log.error("error max bms temperature {}".format(self.bms.get_state()))
            self.set_fsm_state('error')
        elif not self.is_meterhub_ready():
            self.log.error("meterhub error {}".format(self.meterhub.data))
            self.set_fsm_state('error')
        elif self.bms.error:
            self.log.error("bms error {}".format(self.bms.get_state()))
            self.set_fsm_state('error')
        elif not self.is_multiplus_ready():
            self.log.error("multiplus error {}".format(self.multiplus.data))
            self.set_fsm_state('error')
        else:
            if self.mode == 'off' and self._fsm_state != 'off':
                self.set_fsm_state('off')
            elif self.mode == 'auto' and not self._fsm_state.startswith('auto_'):
                self.set_fsm_state('auto_idle')
            elif self.mode == 'manual' and self._fsm_state != 'manual':
                self.set_fsm_state('manual')

    def is_charge_start(self):
        """
        Check charge start condition

        :return: bool
        """
        if self.home_p is None:  # no smartmeter data
            self.charge_start_timer.stop()
            return False
        try:
            p = (self.home_p * -1) + self.get_setting('charge_reserve_power')
        except:
            p = 0

        if p < self.get_setting('charge_min_power') or self.bms.soc_high is None or self.bms.soc_high > (
                self.get_setting('charge_end_soc') - self.get_setting('charge_hysteresis_soc')):
            self.charge_start_timer.stop()
        else:
            if self.charge_start_timer.is_stop():
                self.charge_start_timer.start(self.get_setting('charge_start_time'))
            elif self.charge_start_timer.is_expired():
                # self.charge_start_timer.stop()
                return True
        return False

    def is_feed_start(self):
        """
        Check feed start condition

        :return: bool
        """
        if self.home_p is None:  # no smartmeter data
            self.feed_start_timer.stop()
            return False
        if self.home_p > 0:
            self.hausverbrauch = self.home_p
        else:
            self.hausverbrauch = 0

        try:
            p =  self.hausverbrauch - self.get_setting('feed_reserve_power')
        except:
            p = 0

        # Keine Einspeisung bei mehr als 2kW PV Leistung
        #if self.pv_p > 2000:
        #   p = 0

        if p < self.get_setting('feed_min_power') or self.bms.soc_low is None or self.bms.soc_low < (
                self.get_setting('feed_end_soc') + self.get_setting('feed_hysteresis_soc')):
            self.feed_start_timer.stop()
        else:
            if self.feed_start_timer.is_stop():
                self.feed_start_timer.start(self.get_setting('feed_start_time'))
            elif self.feed_start_timer.is_expired():
                # self.feed_start_timer.stop()
                return True
        return False

    def is_meterhub_ready(self):
        return True if self.meterhub.data and 'error' not in self.meterhub.data else False

    def is_multiplus_ready(self):
        return True if self.multiplus.data and 'error' not in self.multiplus.data else False

    def is_multiplus_on(self):
        """
        Multiplus is running and executes power commands (not sleep, wait after wakeup, init or offline)
        """
        return dictget(self.multiplus.data, 'state') not in (None, 'sleep', 'wait', 'init', 'offline')

    def is_multiplus_hold(self, name):
        """
        Hold regulation in auto_charge / auto_feed until multiplus is on. Go to idle after 30s.

        :param name: 'charge' or 'feed' for log
        :return: True if regulation must be skipped
        """
        if self.is_multiplus_on():
            if self.mp2_wait_timer.is_run():
                self.mp2_wait_timer.stop()
                self.log.info("{} start, multiplus on".format(name))
            return False
        if self.mp2_wait_timer.is_stop():
            self.mp2_wait_timer.start(30)
            self.log.info("{} hold, wait for multiplus on, state={}".format(name, dictget(self.multiplus.data, 'state')))
        elif self.mp2_wait_timer.is_expired():
            self.mp2_wait_timer.stop()
            self.log.warning("{} end, multiplus not on after 30s, state={}".format(name, dictget(self.multiplus.data, 'state')))
            self.set_fsm_state('auto_idle')
        self.set_p = 0
        self.state_timer.stop()  # no end by low power while waiting
        return True

    def handle_power_command(self):
        """
        Raspberry shutdown / reboot from the web interface (manual mode). Handled before the fsm,
        so it also works in error / init state (e.g. multiplus or bms not reachable).
        """
        cmd = self.ui_command.get('manual_cmd') if isinstance(self.ui_command, dict) else None
        if self.mode != 'manual' or cmd not in ('shutdown', 'reboot'):
            return
        self.ui_command.pop('manual_cmd')
        self.log.warning("manual raspberry {} ! (multiplus sleep, {} in 5s)".format(cmd, cmd))
        self.set_p = 0
        self.multiplus.sleep()  # no uncontrolled charge / feed without ess
        opt = '-h' if cmd == 'shutdown' else '-r'
        subprocess.Popen(['/bin/sh', '-c', 'sleep 5; sudo /sbin/shutdown {} now'.format(opt)])

    def is_feed_stuck(self):
        """
        Watchdog in auto_feed: multiplus is on and gets a high feed set value, but delivers no power
        (e.g. latched low battery state after a voltage drop). Restart multiplus by sleep / wakeup,
        same as the manual reset, max FEED_STUCK_MAX_RESTARTS per hour.

        :return: True if a multiplus restart was started
        """
        inv_p = dictget(self.multiplus.data, 'inv_p')
        if self.set_p > -self.FEED_STUCK_POWER or inv_p is None or abs(inv_p) >= self.FEED_STUCK_INV_P \
                or not self.is_multiplus_on():
            self.feed_stuck_timer.stop()
            return False
        if self.feed_stuck_timer.is_stop():
            self.feed_stuck_timer.start(self.FEED_STUCK_TIME)
            return False
        if not self.feed_stuck_timer.is_expired():
            return False
        self.feed_stuck_timer.stop()

        t = time.time()
        self.mp2_restart_times = [x for x in self.mp2_restart_times if t - x < 3600]
        if len(self.mp2_restart_times) >= self.FEED_STUCK_MAX_RESTARTS:
            if not self.mp2_restart_limit_logged:
                self.mp2_restart_limit_logged = True
                self.log.warning("multiplus feed stuck, restart limit {}/h reached".format(self.FEED_STUCK_MAX_RESTARTS))
            return False
        self.mp2_restart_limit_logged = False
        self.mp2_restart_times.append(t)

        m = self.multiplus.data
        self.log.warning("multiplus feed stuck {}s: set_p={}W inv_p={}W state={} device_state={} led={} "
                         "mp2_u={}V mp2_soc={}% bms_u={}V bms_soc={}%".format(
                             self.FEED_STUCK_TIME, self.set_p, inv_p, dictget(m, 'state'), dictget(m, 'device_state_name'),
                             dictget(m, 'led_info'), dictget(m, 'bat_u'), dictget(m, 'soc'), self.bms.voltage, self.bms.soc))
        self.log.warning("multiplus restart {}/{} per hour (sleep / wakeup)".format(
            len(self.mp2_restart_times), self.FEED_STUCK_MAX_RESTARTS))
        self.multiplus.sleep()
        self.mp2_restart_timer.start(self.MP2_RESTART_SLEEP_TIME)  # auto_idle wakes up multiplus after this time
        return True

    # ==================================================================================================================
    #   INIT
    # ==================================================================================================================
    def fsm_init(self, entry):
        if entry:
            self.log.info("FSM: INIT")
            self.set_p = 0
            self.state_timer.start(10)

        if self.is_meterhub_ready() and not self.bms.error and self.is_multiplus_ready():
            self.fsm_switch()

        if self.state_timer.is_expired():
            if not self.is_meterhub_ready():
                self.log.error("meterhub error {}".format(self.meterhub.data))
            if self.bms.error:
                self.log.error("bms error {}".format(self.bms.get_state()))
            if not self.is_multiplus_ready():
                self.log.error("multiplus error={}".format(self.multiplus.data))
            self.set_fsm_state('error')

    # ==================================================================================================================
    #   ERROR
    # ==================================================================================================================
    def fsm_error(self, entry):
        if entry:
            self.log.info("FSM: ERROR")
            self.blackbox.dump()  # save blockbox data to file
            self.set_p = 0
            if self.error_ack_count < self.MAX_ERROR_ACKS_PER_DAY:
                self.error_ack_timer.start(self.ERROR_ACK_INTERVAL)
            else:
                self.log.warning("daily automatic error reset limit reached")

        if self.error_ack_count < self.MAX_ERROR_ACKS_PER_DAY:
            if self.error_ack_timer.is_stop():
                self.error_ack_timer.start(self.ERROR_ACK_INTERVAL)
            elif self.error_ack_timer.is_expired():
                self.error_ack_count += 1
                self.error_ack_timer.stop()
                self.log.warning("automatic error reset {}/{}".format(
                    self.error_ack_count, self.MAX_ERROR_ACKS_PER_DAY))
                self.set_fsm_state('init')

    # ==================================================================================================================
    #   OFF
    # ==================================================================================================================
    def fsm_off(self, entry):
        if entry:
            self.log.info("FSM: OFF")
            self.set_p = 0

    # ==================================================================================================================
    #   AUTO_IDLE
    # ==================================================================================================================
    def fsm_auto_idle(self, entry):
        if entry:
            self.log.info("AUTO-IDLE")
            self.set_p = 0
            self.charge_start_timer.stop()
            self.feed_start_timer.stop()
            if self.get_setting('idle_sleep_time'):  # if >0  use sleep
                self.state_timer.start(self.get_setting('idle_sleep_time'))
        try:
            mp2_state = self.multiplus.data['state']
            if self.mp2_restart_timer.is_expired():
                self.mp2_restart_timer.stop()
                self.log.info("[auto-idle] multiplus restart, sleep time over, state={}".format(mp2_state))

            if self.mp2_restart_timer.is_run():  # multiplus restart (sleep / wakeup) in progress, no wakeup / start
                pass
            elif (self.is_feed_start() or self.is_charge_start()) and mp2_state == 'sleep':
                self.log.info("[auto-idle] wakeup")
                self.state_timer.start(self.get_setting('idle_sleep_time'))
                self.multiplus.wakeup()

            if self.mp2_restart_timer.is_run():
                pass
            elif self.is_multiplus_on():  # regulation only when multiplus is on (not sleep / wait after wakeup)
                if self.is_feed_start():
                    self.set_fsm_state('auto_feed')
                elif self.is_charge_start():
                    self.set_fsm_state('auto_charge')

            # Night charge
            if (self.get_setting('charge_night_end_soc') > 0) and (self.bms.soc < self.get_setting('charge_night_end_soc')):
                if (int(time.strftime("%H")) == 1) and (int(time.strftime("%M")) == 0):
                     self.set_fsm_state('auto_night_charge')
                     if mp2_state=='sleep':
                          self.multiplus.wakeup()

            if self.state_timer.is_expired() and mp2_state != 'sleep':
                self.state_timer.start(5)  # resend
                self.log.info("[auto-idle] sleep")
                self.multiplus.sleep()

        except Exception as e:
            self.log.error("[auto_idle] exception {}".format(e))
            self.set_fsm_state('error')

    # ==================================================================================================================
    #   AUTO_NIGHT_CHARGE
    # ==================================================================================================================

    def fsm_auto_night_charge(self, entry):

        if entry:
            self.log.info("AUTO-NIGHT-CHARGE")

        try:
            if self.bms.soc >= self.get_setting('charge_night_end_soc'):  # end by night soc
                self.log.info("night charge end by soc (config.charge_night_end_soc)")
                self.set_p = 0
                self.set_fsm_state('auto_idle')
            elif self.bms.soc_high and self.bms.soc_high >= self.get_setting('charge_end_soc'):  # end by SOC
                self.log.info("night charge end by soc (config.charge_end_soc)")
                self.set_p = 0
                self.set_fsm_state('auto_idle')
            elif self.bms.voltage and self.bms.voltage >= self.get_setting('charge_end_voltage'):  # end by UDC
                self.log.info("night charge end by voltage (config.charge_end_voltage)")
                self.set_p = 0
                self.set_fsm_state('auto_idle')
            elif int(time.strftime("%H")) >= 4:  # end by time, night charge starts at 01:00
                self.log.info("night charge end by time")
                self.set_p = 0
                self.set_fsm_state('auto_idle')
            else:
                self.set_p = self.get_setting('charge_max_power')

        except Exception as e:
            self.log.error("[auto_night_charge] exception {}".format(e))
            self.set_fsm_state('error')


    # ==================================================================================================================
    #   AUTO_CHARGE
    # ==================================================================================================================
    def fsm_auto_charge(self, entry):
        if entry:
            self.log.info("AUTO-CHARGE")
            self.reg_p = 10
            self.mp2_wait_timer.stop()

        if self.home_p is None:  # smartmeter (AMIS) missing -> idle
            self.log.warning("charge end, smartmeter data missing")
            self.set_p = 0
            self.set_fsm_state('auto_idle')
            return

        if self.is_multiplus_hold('charge'):  # multiplus not on (e.g. wait after wakeup), no regulation
            return

        try:
            #p = self.pv_p - self.get_setting('charge_reserve_power')
            if self.home_p > -30 and self.home_p < 0:  # deadband, target 0 W at grid meter
                self.reg_p = self.reg_p
            elif self.home_p < -30:  # grid export -> charge more
                self.reg_p = self.reg_p + round(-self.home_p * self.gain)
            elif self.home_p > 0:  # grid import -> charge less (fast down)
                self.reg_p = self.reg_p - round(self.home_p * self.gain_down)

            if self.reg_p > self.get_setting('charge_max_power'):
                self.reg_p = self.get_setting('charge_max_power')
            if self.reg_p < 0:
                self.reg_p = 0
            if self.bms.soc >= 95 and self.reg_p > 500:
                self.reg_p = 500
            if self.bms.soc >= 97 and self.reg_p > 300:
                self.reg_p = 300

            #print("p={} pv={} home_all={} home={} car={}".format(p, self.pv_p, self.home_all_p, self.home_p, self.car_p) )
            # ToDo Filter     schnell runter, langsam hoch

            charge_set_p = limit(self.reg_p, 0, self.get_setting('charge_max_power'))  # limit to 0..max
            if self.bms.soc_high and self.bms.soc_high >= self.get_setting('charge_end_soc'):  # end by SOC
                self.log.info("charge end by soc (config.charge_end_soc)")
                self.set_fsm_state('auto_idle')
            elif self.bms.voltage and self.bms.voltage >= self.get_setting('charge_end_voltage'):  # end by UDC
                self.log.info("charge end by voltage (config.charge_end_voltage)")
                self.set_fsm_state('auto_idle')
            else:
                if charge_set_p > self.get_setting('charge_min_power'):
                    self.state_timer.stop()
                else:
                    if self.state_timer.is_stop():
                        self.state_timer.start(self.get_setting('charge_stop_time'))
                    elif self.state_timer.is_expired():
                        self.log.info(
                            "end by low charge power, home={}W pv={}W".format(self.home_p, self.pv_p))
                        self.set_fsm_state('auto_idle')

            self.set_p = charge_set_p

        except Exception as e:
            self.log.error("[auto_charge] exception {}".format(e))
            self.set_fsm_state('error')

    # ==================================================================================================================
    #   AUTO_FEED
    # ==================================================================================================================
    def fsm_auto_feed(self, entry):
        if entry:
            self.log.info("AUTO-FEED")
            self.reg_p = 10
            self.mp2_wait_timer.stop()

        if self.home_p is None:  # smartmeter (AMIS) missing -> idle
            self.log.warning("feed end, smartmeter data missing")
            self.set_p = 0
            self.set_fsm_state('auto_idle')
            return

        if self.is_multiplus_hold('feed'):  # multiplus not on (e.g. wait after wakeup), no regulation
            return

        try:
            #p = self.home_p - self.pv_p - self.get_setting('feed_reserve_power')
            t_min, t_max = self.feed_target  # target: small grid import, no battery power to grid
            feed_err = self.home_p - (t_min + t_max) / 2
            if t_min <= self.home_p <= t_max:  # deadband, inside target range
                self.reg_p = self.reg_p
            elif feed_err > 0:  # grid import above target -> feed more
                self.reg_p = self.reg_p + round(feed_err * self.gain)
            else:  # below target / grid export -> feed less (fast down)
                self.reg_p = self.reg_p + round(feed_err * self.gain_down)

            if self.reg_p > self.get_setting('feed_max_power'):
                self.reg_p = self.get_setting('feed_max_power')
            if self.reg_p < 0:
                self.reg_p = 0  # no integrator windup at grid export

            if self.bms.soc < 25:
                max_p = self.get_setting('feed_soc25_max_power')
            else:
                max_p = self.get_setting('feed_max_power')

            feed_set_p = limit(self.reg_p, 0, max_p)  # limit to 0..max

            # ------ throttle --------------
            if not self.feed_throttle:
                if feed_set_p < self.get_setting('feed_throttle_power'):
                    self.feed_throttle_timer.stop()
                else:
                    if self.feed_throttle_timer.is_stop():
                        self.feed_throttle_timer.start(self.get_setting('feed_throttle_time'))
                if self.feed_throttle_timer.is_expired():
                    self.feed_throttle = True
                    self.log.info("feed throttle activated")
            else:
                if feed_set_p > self.get_setting('feed_throttle_power'):
                    self.feed_throttle_timer.stop()
                else:
                    if self.feed_throttle_timer.is_stop():
                        self.feed_throttle_timer.start(self.get_setting('feed_throttle_time'))
                if self.feed_throttle_timer.is_expired():
                    self.feed_throttle = False
                    self.log.info("feed throttle disabled")

                feed_set_p = limit(self.reg_p, 0, self.get_setting('feed_throttle_power'))
            # --------------------------------------------------------------------------------

            if self.bms.soc_low and self.bms.soc_low <= self.get_setting('feed_end_soc'):  # end by SOC
                self.log.info("feed end by soc (config.feed_end_soc)")
                self.set_fsm_state('auto_idle')
            elif self.bms.voltage and self.bms.voltage <= self.get_setting('feed_end_voltage'):  # end by UDC
                self.log.info("feed end by voltage (config.feed_end_voltage)")
                self.set_fsm_state('auto_idle')
            else:
                if feed_set_p > self.get_setting('feed_min_power'):
                    self.state_timer.stop()
                else:
                    if self.state_timer.is_stop():
                        self.state_timer.start(self.get_setting('feed_stop_time'))
                    elif self.state_timer.is_expired():
                        self.log.info(
                            "end by low feed power (config.feed_min_power) home={}W pv={}W".format(self.home_p,
                                                                                                   self.pv_p))
                        self.set_fsm_state('auto_idle')

            self.set_p = -feed_set_p

            if self.is_feed_stuck():  # multiplus on, but no feed -> restart multiplus (sleep / wakeup)
                self.set_p = 0
                self.set_fsm_state('auto_idle')
                return

            # Night charge
            if (self.get_setting('charge_night_end_soc') > 0) and (self.bms.soc < self.get_setting('charge_night_end_soc')):
                if (int(time.strftime("%H")) == 1) and (int(time.strftime("%M")) == 0):
                    self.set_p = 0
                    self.set_fsm_state('auto_night_charge')

        except Exception as e:
            self.log.error("[auto_feed] exception {}".format(e))
            self.set_fsm_state('error')

    # ==================================================================================================================
    #   MANUAL
    # ==================================================================================================================
    def fsm_manual(self, entry):
        if entry:
            self.log.info("MANUAL")
            self.set_p = 0
            self.state_timer.start(50000)

        if self.ui_command and 'manual_set_p' in self.ui_command:
            self.state_timer.start(50000)
            self.log.info("manual command by api: {}".format(self.ui_command))
            try:
                self.set_p = self.ui_command['manual_set_p']

                cmd = self.ui_command.get('manual_cmd', None)
                if cmd == 'sleep':
                    self.log.info("manual multiplus sleep !")
                    self.multiplus.sleep()
                elif cmd == 'wakeup':
                    self.log.info("manual multiplus wakeup !")
                    self.multiplus.wakeup()
            except:
                self.set_p = 0

        self.ui_command = None

        if self.state_timer.is_expired():
            self.log.info("manual timer expired")
            self.mode = 'off'

    def get_state(self, bms_detail=False):

        """
        Get current state as dictionary (for API)

        :return: dictionary
        """
        d = {
            'ess': {
                'mode': self.mode,
                'state': self._fsm_state,
                'set_p': self.set_p,
                'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'setting': self.setting,
                'info': self.get_info_text()
            },
            'meterhub': self.meterhub.data,
            'bms': self.bms.get_state(),
            'multiplus': self.multiplus.data,
        }
        if bms_detail:
            d['bms_detail'] = self.bms.get_detail()
        return d

    def get_info_text(self):
        """
        Get status as german text string

        :return: string
        """
        try:
            mp2_state = self.multiplus.data['state']

            s = '[{}, {}, {}]'.format(self.mode, self._fsm_state, mp2_state)
            if self.mode == 'off':
                s = "AUS"
            elif self.mode == 'manual':
                s = "HANDBETRIEB !"
            elif self._fsm_state == 'auto_idle' and mp2_state == 'sleep':
                s = "Automatik - Schlafen"
            elif self._fsm_state == 'auto_idle' and mp2_state == 'on':
                s = "Automatik - Bereit"
            elif self._fsm_state == 'auto_charge' and mp2_state == 'on':
                s = "Automatik - Laden"
            elif self._fsm_state == 'auto_feed' and mp2_state == 'on':
                s = "Automatik - Einspeisen"
            elif self._fsm_state == 'auto_night_charge' and mp2_state == 'on':
                s = "Automatik - Nachtladen"
            elif mp2_state == 'wait':
                s = "Automatik - Warten"
            return s
        except:
            return ''
