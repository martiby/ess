import time
import logging
from bms_us2000 import US2000

logging.basicConfig(
    level=logging.INFO,   # DEBUG  INFO
    format='%(asctime)s %(name)-10s %(levelname)-6s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

# port = '/dev/ttyACM0'
port = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_556F023975-if00"  # Raspberry Home (rechts oben)

us2000 = US2000(port, pack_number=1)
while True:
    print(us2000.get_state())
    time.sleep(1)
