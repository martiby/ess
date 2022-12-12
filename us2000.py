import logging
import time
from datetime import datetime
from threading import Thread

import serial  # pip install pyserial

from pylontech import read_analog_value, read_alarm_info

"""
Pylontech / US2000 service class for cyclic polling inside a thread. 

See demo_us2000.py for a simple example. 

{
'analog': [
            {'u_cell': (3225, 3224, 3225, 3224, 3226, 3226, 3225, 3226, 3228, 3225, 3227, 3227, 3227, 3226, 3225), 
            't': [17.5, 16.8, 16.9, 16.5, 17.2], 
            'q': 6415, 'q_total': 50000, 'cycle': 132, 'i': -0.1, 'u': 48.386, 'soc': 13},
             
            {'u_cell': (3229, 3228, 3229, 3226, 3227, 3227, 3227, 3226, 3228, 3228, 3229, 3226, 3226, 3228, 3228), 
             't': [20.0, 17.0, 16.0, 17.0, -100.0], 
             'q': 4815, 'q_total': 50000, 'cycle': 376, 'i': 0.0, 'u': 48.412, 'soc': 10}
            ], 
'alarm': [
            {'u_cell': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 
             't': [0, 0, 0, 0, 0], 'i_chg': 0, 'u_pack': 0, 'i_dis': 0, 'status': [0, 14, 64, 0, 0], 'ready': True}, 
              
            {'u_cell': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 
             't': [0, 0, 0, 0, 0], 'i_chg': 0, 'u_pack': 0, 'i_dis': 0, 'status': [0, 14, 0, 0, 0], 'ready': True}
         ],
'analog_timeout': [22300564.212521262, 22300564.212521262], 
'alarm_timeout': [22300564.212521262, 22300564.212521262]  
}

30.11.2022  Martin Steppuhn     Split in pylontech.py (baisc packets) and us2000.py (threaded service class) 
"""


class US2000:
    def __init__(self, port=None, baudrate=115200, pack_number=1, lifetime=10, log_name='us2000', pause=0.25):
        """
        Service class with polling thread

        :param port:        Serial port, '/dev/ttyUSB0'
        :param baudrate:    Integer, 9600, 115200,  ...
        :param pack_number: Number of packs
        :param lifetime:    Time in seconds data is still valid
        :param log_name:    Name
        :param pause:       Pause between polling
        """
        self.port = port
        self.baudrate = baudrate  # save baudrate
        self.pack_number = pack_number  # number of devices
        self.pause = pause
        self.lifetime = lifetime
        self.log = logging.getLogger(log_name)
        self.log.info('init port={}'.format(port))
        self.com = None
        self.data = {
            'ready': False,
            'error': None,
            'u': None,
            'i': None,
            't': None,
            'soc': None,
            'u_pack': [None] * self.pack_number,
            'i_pack': [None] * self.pack_number,
            't_pack': [None] * self.pack_number,
            'soc_pack': [None] * self.pack_number,
            'cycle_pack': [None] * self.pack_number,
        }
        self.data_detail = {"analog": [None] * pack_number,
                            "alarm": [None] * pack_number,
                            "analog_timeout": [time.perf_counter() + self.lifetime] * pack_number,
                            "alarm_timeout": [time.perf_counter() + self.lifetime] * pack_number}

        self.connect()
        self.thread = Thread(target=self.run, daemon=True)
        self.thread.start()

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

            for i in range(self.pack_number):
                try:
                    d = read_analog_value(self.com, i)
                    self.log.debug("read_analog_value[{}] {}".format(i, d))
                    self.data_detail['analog'][i] = d
                    self.data_detail['analog'][i]['time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.data_detail['analog_timeout'][i] = time.perf_counter() + self.lifetime
                except IOError:
                    self.com = None
                    self.log.error("read_analog_value: io port failed")
                except Exception as e:
                    self.log.debug("EXCEPTION read_analog_value[{}] {}".format(i, e))

                self.update()
                time.sleep(self.pause)

                try:
                    d = read_alarm_info(self.com, i)
                    self.log.debug("read_alarm_info[{}] {}".format(i, d))
                    self.data_detail['alarm'][i] = d
                    self.data_detail['alarm'][i]['time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.data_detail['alarm_timeout'][i] = time.perf_counter() + self.lifetime
                except IOError:
                    self.com = None
                    self.log.error("read_alarm_info: io port failed")
                except Exception as e:
                    self.log.debug("EXCEPTION read_alarm_info[{}] {}".format(i, e))

                self.update()
                time.sleep(self.pause)




    def update(self):
        t = time.perf_counter()

        error = None
        ready = True

        for i in range(self.pack_number):
            try:
                if self.data_detail['alarm'][i]['error']:    # active error
                    error = 'alarm'
                if self.data_detail['alarm'][i]['ready'] is False:   # not ready
                    ready = False
            except:
                pass

            try:
                if self.data_detail['analog'][i]:
                    self.data['u_pack'][i] = self.data_detail['analog'][i]['u']
                    self.data['i_pack'][i] = self.data_detail['analog'][i]['i']
                    self.data['soc_pack'][i] = self.data_detail['analog'][i]['soc']
                    self.data['cycle_pack'][i] = self.data_detail['analog'][i]['cycle']
                    self.data['t_pack'][i] = max(self.data_detail['analog'][i]['t'])
            except Exception:
                self.log.exception("update failed")
                pass

            if t > self.data_detail['analog_timeout'][i]:
                self.data_detail['analog'][i] = None
                error = 'timeout'
                ready = False

            if t > self.data_detail['alarm_timeout'][i]:
                self.data_detail['alarm'][i] = None
                error = 'timeout'
                ready = False

        try:
            self.data['u'] = max(self.data['u_pack'])
            self.data['t'] = max(self.data['t_pack'])
            self.data['soc'] = round(sum(self.data['soc_pack']) / self.pack_number)
        except:
            pass

        self.data['error'] = error
        self.data['ready'] = ready

