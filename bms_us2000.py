from bms import BMS
import logging
import time
from datetime import datetime
from threading import Thread
from pylontech import read_analog_value, read_alarm_info
import serial  # pip install pyserial


class US2000(BMS):

    def __init__(self, port=None, baudrate=115200, pack_number=1, lifetime=20, log_name='us2000', pause=0.25, type='US2000'):
        """
        Service class with polling thread

        :param port:        Serial port, '/dev/ttyUSB0'
        :param baudrate:    Integer, 9600, 115200,  ...
        :param pack_number: Number of packs
        :param lifetime:    Time in seconds data is still valid
        :param log_name:    Name
        :param pause:       Pause between polling
        """
        super().__init__()
        self.port = port
        self.baudrate = baudrate  # save baudrate
        self.pack_number = pack_number  # number of devices
        self.type = type   # 'US5000'   default 'US2000' or 'US3000'
        self.pause = pause
        self.lifetime = lifetime
        self.log = logging.getLogger(log_name)
        self.log.info('init port={}'.format(port))
        self.com = None

        self._pack_u = [None] * self.pack_number
        self._pack_i = [None] * self.pack_number
        self._pack_t = [None] * self.pack_number
        self._pack_soc = [None] * self.pack_number
        self._pack_cycle = [None] * self.pack_number

        self.data = {"analog": [None] * pack_number,
                     "alarm": [None] * pack_number,
                     "analog_timeout": [time.perf_counter() + self.lifetime] * pack_number,
                     "alarm_timeout": [time.perf_counter() + self.lifetime] * pack_number,
                     "frame_count": 0,
                     "error_analog": [0] * self.pack_number,
                     "error_alarm": [0] * self.pack_number}

        self.connect()
        self.thread = Thread(target=self.run, daemon=True)
        self.thread.start()

    def get_state(self):
        """
        Get status of BMS as dictionary
        """
        return {
            'error': self._error,
            'u': self._voltage,
            'i': self._current,
            't': self._temperature,
            'soc': self._soc,
            'soc_low': self._soc_low,
            'soc_high': self._soc_high,

            'pack_u': self._pack_u,
            'pack_i': self._pack_i,
            'pack_t': self._pack_t,
            'pack_soc': self._pack_soc,
            'pack_cycle': self._pack_cycle,
        }

    def get_detail(self):
        """
        Get extra status of BMS as dictionary
        """
        return self.data

    def connect(self):
        try:
            self.com = serial.Serial(self.port, baudrate=self.baudrate, timeout=0.5)  # non blocking
        except Exception as e:
            self.com = None
            self.log.error("connect: {}".format(e))

    def run(self):
        while True:
            if self.com is None:
                self.connect()
            else:
                self.data['frame_count'] += 1  # count read cycle

            for i in range(self.pack_number):
                try:
                    d = read_analog_value(self.com, i, self.type)
                    self.log.debug("read_analog_value[{}] {}".format(i, d))
                    self.data['analog'][i] = d
                    self.data['analog'][i]['time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.data['analog_timeout'][i] = time.perf_counter() + self.lifetime
                except IOError:
                    self.com = None
                    self.data['analog'][i] = None
                    self.log.error("read_analog_value: io port failed")
                except Exception as e:
                    self.data['analog'][i] = None
                    self.data['error_analog'][i] += 1  # count error
                    self.log.debug("EXCEPTION read_analog_value[{}] {}".format(i, e))

                time.sleep(self.pause)

                try:
                    d = read_alarm_info(self.com, i)
                    self.log.debug("read_alarm_info[{}] {}".format(i, d))
                    self.data['alarm'][i] = d
                    self.data['alarm'][i]['time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.data['alarm_timeout'][i] = time.perf_counter() + self.lifetime
                except IOError:
                    self.com = None
                    self.data['alarm'][i] = None
                    self.log.error("read_alarm_info: io port failed")
                except Exception as e:
                    self.data['alarm'][i] = None
                    self.data['error_alarm'][i] += 1  # count error
                    self.log.debug("EXCEPTION read_alarm_info[{}] {}".format(i, e))

                time.sleep(self.pause)

            self.process_data()

    def process_data(self):
        """
        Convert raw bms data to BMS main values (voltage, current, soc, ...)
        """
        t = time.perf_counter()

        valid = True
        error = None

        for i in range(self.pack_number):  # loop over all packs
            try:
                if self.data['alarm'][i]['error']:  # active error
                    error = 'alarm pack {}'.format(i)
            except:
                pass

            try:
                self._pack_u[i] = self.data['analog'][i]['u']
                self._pack_i[i] = self.data['analog'][i]['i']
                self._pack_t[i] = max(self.data['analog'][i]['t'])
                self._pack_soc[i] = self.data['analog'][i]['soc']
                self._pack_cycle[i] = self.data['analog'][i]['cycle']
            except:
                valid = False
                self._pack_u[i] = None
                self._pack_i[i] = None
                self._pack_t[i] = None
                self._pack_soc[i] = None
                self._pack_cycle[i] = None
                self.log.exception("process_data with pack {} failed".format(i))

            if t > self.data['analog_timeout'][i] or t > self.data['alarm_timeout'][i]:
                error = "timeout pack {}".format(i)

        # process all packs to main data

        if valid:
            try:
                self._voltage = max(self._pack_u)
                self._current = sum(self._pack_i)
                self._temperature = max(self._pack_t)
                self._soc = round(sum(self._pack_soc) / self.pack_number)
                self._soc_low = round(min(self._pack_soc))
                self._soc_high = round(max(self._pack_soc))
                self._error = None
            except:
                self._error = "exception"

        if error:
            self._error = error
            self._voltage = None
            self._current = None
            self._temperature = None
            self._soc = None
            self._soc_low = None
            self._soc_high = None

    def update(self):
        """
        not used because of threaded implementation
        """
        pass
