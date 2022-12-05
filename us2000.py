import logging
import time
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
'analog_update': [22300564.212521262, 22300564.212521262], 
'alarm_update': [22300564.212521262, 22300564.212521262]  
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
        self.data = None
        self.data_detail = {"analog": [None] * pack_number,
                          "alarm": [None] * pack_number,
                          "analog_update": [time.perf_counter()] * pack_number,
                          "alarm_update": [time.perf_counter()] * pack_number}

        self.connect()
        self.thread = Thread(target=self.run, daemon=True)
        self.thread.start()

    def connect(self):
        try:
            self.com = serial.Serial(self.port, baudrate=self.baudrate, timeout=0.5)  # non blocking
        except Exception as e:
            self.com = None
            self.log.error("connect: {}".format(e))

    def update(self):
        d = {
            'u': None,
            'soc': None,
            't': None,
            'ready': False,
            'u_pack': [None] * self.pack_number,
            'i_pack': [None] * self.pack_number,
            'soc_pack': [None] * self.pack_number,
            'cycle_pack': [None] * self.pack_number,
            't_pack': [None] * self.pack_number
        }

        ready_cnt = 0

        for i in range(self.pack_number):
            try:
                if self.data_detail['analog'][i]:
                    d['u_pack'][i] = self.data_detail['analog'][i]['u']
                    d['i_pack'][i] = self.data_detail['analog'][i]['i']
                    d['soc_pack'][i] = self.data_detail['analog'][i]['soc']
                    d['cycle_pack'][i] = self.data_detail['analog'][i]['cycle']
                    d['t_pack'][i] = max(self.data_detail['analog'][i]['t'])
            except:
                pass

            try:
                if self.data_detail['alarm'][i]['error']:
                    d['error'] = 'alarm'
            except:
                pass

            try:
                if self.data_detail['alarm'][i]['ready'] is True:
                    ready_cnt += 1
            except:
                pass

            t = time.perf_counter()
            if t > self.data_detail['analog_update'][i] + self.lifetime or t > self.data_detail['alarm_update'][i] + self.lifetime:

                if self.com is None:
                    d['error'] = 'could not open port'
                else:
                    d['error'] = 'timeout'

        try:
            d['u'] = max(d['u_pack'])
            d['t'] = max(d['t_pack'])
            d['soc'] = round(sum(d['soc_pack']) / self.pack_number)
            d['ready'] = True if ready_cnt == self.pack_number and 'error' not in d else False
        except:
            pass




        self.data = d

    def run(self):
        while True:
            if self.com is None:
                self.connect()



            for i in range(self.pack_number):
                try:
                    d = read_analog_value(self.com, i)
                    self.log.debug("read_analog_value[{}] {}".format(i, d))
                    self.data_detail['analog'][i] = d
                    self.data_detail['analog_update'][i] = time.perf_counter()
                except IOError:
                    self.com = None
                    self.log.error("read_analog_value: io port failed")
                except Exception as e:
                    self.log.debug("EXCEPTION read_analog_value[{}] {}".format(i, e))

                self.update()
                time.sleep(self.pause)

            for i in range(self.pack_number):
                try:
                    d = read_alarm_info(self.com, i)
                    self.log.debug("read_alarm_info[{}] {}".format(i, d))
                    self.data_detail['alarm'][i] = d
                    self.data_detail['alarm_update'][i] = time.perf_counter()
                except IOError:
                    self.com = None
                    self.log.error("read_alarm_info: io port failed")
                except Exception as e:
                    self.log.debug("EXCEPTION read_alarm_info[{}] {}".format(i, e))

                self.update()
                time.sleep(self.pause)
