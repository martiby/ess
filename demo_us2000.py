import time
import logging
from bms_us2000 import US2000

logging.basicConfig(
    level=logging.INFO,   # DEBUG  INFO
    format='%(asctime)s %(name)-10s %(levelname)-6s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

# port = '/dev/ttyACM0'
port = "/dev/serial/by-path/platform-3f980000.usb-usb-0:1.3:1.0"  # Raspberry Home (rechts oben)

us2000 = US2000(port, pack_number=2)
while True:
    print(us2000.get_state())
    time.sleep(1)
