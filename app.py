import logging
import time
from copy import deepcopy
from datetime import datetime

import version
from api_request import ApiRequest
from config import config
from fsm import FSM
from multiplus2 import MultiPlus2
from us2000 import US2000
from timer import Timer
from trace import Trace
from utils import *
from web import AppWeb

"""
ESS Application
"""

class App(FSM):
    def __init__(self):
        super().__init__('init')
        self.www_path = 'www'
        self.log = logging.getLogger('app')
        self.web = AppWeb(self)
        self.trace = Trace()
        self.config = config
        self.meterhub = ApiRequest(config['meterhub_address'], timeout=0.5, lifetime=10, log_name='meterhub')
        self.bms = US2000(port=config['pylontech_bms_port'], pack_number=config['us2000_pack_number'], lifetime=20, log_name='bms')
        self.multiplus = MultiPlus2(config['victron_mk3_port'])

        self.mode = 'off'  # Operation mode: 'off', 'auto', 'manual'
        self.set_p = 0  # power set value
        self.setting = 0  # 0, 1, ... Index to usersettings from config/ui

        self.ui_command = None  # commands from UI sent with polling, manual commands
        self.feed_throttle = False  # limit max feed at high continous feed

        # values from MeterHub and BMS
        self.grid_p = 0
        self.home_p = 0
        self.home_all_p = 0
        self.bat_p = 0
        self.car_p = 0
        self.pv_p = 0
        self.soc = None
        self.soc_low = None  # lowest SOC
        self.soc_high = None  # highest SOC
        self.ubat = None

        self.charge_start_timer = Timer()
        self.feed_start_timer = Timer()
        self.feed_throttle_timer = Timer()
        self.state_timer = Timer()

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

    def start(self):
        """
        Application mainloop
        """
        self.log.info('start ess {}'.format(version.__version__))

        while True:
            t_begin = time.perf_counter()  # cycle start time

            # === meterhub ===================================================   ~ 15ms

            self.meterhub.read(
                post={'bat_info': self.get_info_text(), 'bat_soc': dictget(self.bms.data, 'soc')})
            self.log.debug("meterhub {}".format(self.meterhub.data))

            # === bms ===================================================   ~ 0ms (Thread)

            self.log.debug("bms {}".format(self.bms.data))

            # ================================================================

            if self._fsm_state not in ('error', 'init'):
                self.fsm_switch()
            self.update_in()
            self.run_fsm()
            self.trace.push(deepcopy(self.get_state()))

            # === Multiplus ===================================================

            self.multiplus.command(self.set_p)
            time.sleep(0.075)
            self.multiplus.update(pause_time=0.075)
            self.log.debug("multiplus {}".format(self.multiplus.data))

            # ================================================================

            t_end = time.perf_counter()
            while time.perf_counter() < t_begin + 0.75:
                time.sleep(0.01)

            # typical ~ 680ms (synced to 750ms)

            # print("loop {:.3f}s/{:.3f}s ".format(t_end - t_begin, time.perf_counter() - t_begin))

    def update_in(self):
        """
        Acquire all incoming data
        """
        self.grid_p = dictget(self.meterhub.data, 'grid_p')
        self.bat_p = dictget(self.meterhub.data, 'grid_p')
        self.car_p = dictget(self.meterhub.data, 'car_p')
        self.pv_p = dictget(self.meterhub.data, 'pv_p')
        self.home_all_p = dictget(self.meterhub.data, 'home_all_p')

        if self.home_all_p and self.car_p:
            self.home_p = self.home_all_p - self.car_p
        if self.home_all_p:
            self.home_p = self.home_all_p
        else:
            self.home_p = None

        self.soc = dictget(self.bms.data, 'soc')

        try:
            self.soc_low = min(self.bms.data['soc_pack'])
            self.soc_high = max(self.bms.data['soc_pack'])
        except:
            self.soc_low = None
            self.soc_high = None

        self.ubat = dictget(self.bms.data, 'u')


    def fsm_switch(self):
        """
        Auto state change by events
        """
        if dictget(self.bms.data, 'u', 0) > self.config['udc_max']:
            self.log.error("error max voltage at bms {}".format(self.bms.data))
            self.set_fsm_state('error')
        elif dictget(self.multiplus.data, 'bat_u', 0) > self.config['udc_max']:
            self.log.error("error max voltage at multiplus {}".format(self.multiplus.data))
            self.set_fsm_state('error')
        elif dictget(self.bms.data, 't', 0) > self.config['t_max']:
            self.log.error("error max bms temperature {}".format(self.bms.data))
            self.set_fsm_state('error')
        elif not self.is_meterhub_ready():
            self.log.error("meterhub error {}".format(self.meterhub.data))
            self.set_fsm_state('error')
        elif not self.is_bms_ready():
            self.log.error("bms not ready {}".format(self.bms.data))
            self.set_fsm_state('error')
        elif self.is_bms_error():
            self.log.error("bms error {}".format(self.bms.data))
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
        try:
            p = self.pv_p - self.home_all_p - self.get_setting('charge_reserve_power')
        except:
            p = 0

        if p < self.get_setting('charge_min_power') or self.soc_high > (
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

        try:
            p = self.home_p - self.pv_p - self.get_setting('feed_reserve_power')
        except:
            p = 0

        if p < self.get_setting('feed_min_power') or self.soc_low < (
                self.get_setting('feed_end_soc') + self.get_setting('feed_hysteresis_soc')):
            self.feed_start_timer.stop()
        else:
            if self.feed_start_timer.is_stop():
                self.feed_start_timer.start(self.get_setting('feed_start_time'))
            elif self.feed_start_timer.is_expired():
                # self.feed_start_timer.stop()
                return True
        return False

    def is_bms_error(self):
        return True if self.bms.data and 'error' in self.bms.data else False

    def is_bms_ready(self):
        return True if self.bms.data and 'ready' in self.bms.data else False

    def is_meterhub_ready(self):
        return True if self.meterhub.data and 'error' not in self.meterhub.data else False

    def is_multiplus_ready(self):
        return True if self.multiplus.data and 'error' not in self.multiplus.data else False

    # ==================================================================================================================
    #   INIT
    # ==================================================================================================================
    def fsm_init(self, entry):
        if entry:
            self.log.info("FSM: INIT")
            self.set_p = 0
            self.state_timer.start(10)

        if self.is_meterhub_ready() and self.is_bms_ready() and self.is_multiplus_ready():
            self.fsm_switch()

        if self.state_timer.is_expired():
            if not self.is_meterhub_ready():
                self.log.error("meterhub error {}".format(self.meterhub.data))
            if not self.is_bms_ready():
                self.log.error("bms not ready {}".format(self.bms.data))
            if self.is_bms_error():
                self.log.error("bms error {}".format(self.bms.data))
            if not self.is_multiplus_ready():
                self.log.error("multiplus error={}".format(self.multiplus.data))
            self.set_fsm_state('error')

    # ==================================================================================================================
    #   ERROR
    # ==================================================================================================================
    def fsm_error(self, entry):
        if entry:
            self.log.info("FSM: ERROR")
            self.set_p = 0

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
            if (self.is_feed_start() or self.is_charge_start()) and mp2_state == 'sleep':
                self.log.info("[auto-idle] wakeup")
                self.state_timer.start(self.get_setting('idle_sleep_time'))
                self.multiplus.wakeup()

            if self.is_feed_start():
                self.set_fsm_state('auto_feed')
            elif self.is_charge_start():
                self.set_fsm_state('auto_charge')

            if self.state_timer.is_expired() and mp2_state != 'sleep':
                self.state_timer.start(5)  # resend
                self.log.info("[auto-idle] sleep")
                self.multiplus.sleep()

        except Exception as e:
            self.log.error("[auto_idle] exception {}".format(e))
            self.set_fsm_state('error')

    # ==================================================================================================================
    #   AUTO_CHARGE
    # ==================================================================================================================
    def fsm_auto_charge(self, entry):
        if entry:
            self.log.info("AUTO-CHARGE")
        try:
            p = self.pv_p - self.home_all_p - self.get_setting('charge_reserve_power')

            # print("p={} pv={} home_all={} home={} car={}".format(p, self.pv_p, self.home_all_p, self.home_p, self.car_p) )
            # ToDo Filter     schnell runter, langsam hoch

            charge_set_p = limit(p, 0, self.get_setting('charge_max_power'))  # limit to 0..max
            if self.soc_high >= self.get_setting('charge_end_soc'):  # end by SOC
                self.log.info("charge end by soc (config.charge_end_soc)")
                self.set_fsm_state('auto_idle')
            elif self.ubat >= self.get_setting('charge_end_voltage'):  # end by UDC
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

        try:
            p = self.home_p - self.pv_p - self.get_setting('feed_reserve_power')
            feed_set_p = limit(p, 0, self.get_setting('feed_max_power'))  # limit to 0..max

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

                feed_set_p = limit(p, 0, self.get_setting('feed_throttle_power'))
            # --------------------------------------------------------------------------------

            if self.soc_low <= self.get_setting('feed_end_soc'):  # end by SOC
                self.log.info("feed end by soc (config.feed_end_soc)")
                self.set_fsm_state('auto_idle')
            elif self.ubat <= self.get_setting('feed_end_voltage'):  # end by UDC
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
            self.state_timer.start(5)

        if self.ui_command and 'manual_set_p' in self.ui_command:
            self.state_timer.start(5)
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

    def get_state(self):
        """
        Get current state as dictionary (for API)

        :return: dictionary
        """
        return {
            'ess': {
                'mode': self.mode,
                'state': self._fsm_state,
                'set_p': self.set_p,
                'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'setting': self.setting,
                'info': self.get_info_text()
            },
            'meterhub': self.meterhub.data,
            'bms': self.bms.data,
            'multiplus': self.multiplus.data,
        }

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
            elif mp2_state == 'wait':
                s = "Automatik - Warten"
            return s
        except:
            return ''