import time
import serial
from pylontech import *

# port = '/dev/ttyACM0'
port = "/dev/serial/by-path/platform-3f980000.usb-usb-0:1.3:1.0"  # Raspberry Home (rechts oben)

pack_number = 2

com = serial.Serial(port, baudrate=115200, timeout=0.5)  # non blocking

# === serial_number ===

for i in range(pack_number):
    try:
        d = read_serial_number(com, i)
        print(d)
    except Exception as e:
        print("Exception", e)
    time.sleep(1)

# === manufacturer_info ===   ACHTUNG !!!  im Verbund nicht zuverlässig !!!

for i in range(pack_number):
    try:
        d = read_manufacturer_info(com, i)
        print(d)
    except Exception as e:
        print("Exception", e)
    time.sleep(1)

while True:

    # === analog_value ===

    for i in range(pack_number):
        try:
            d = read_analog_value(com, i)
            print(i, d)
        except Exception as e:
            print("Exception", e)

        time.sleep(2)

    # === alarm_info ===

    for i in range(pack_number):
        try:
            d = read_alarm_info(com, i)
            print(i, d)
        except Exception as e:
            print("Exception", e)

        time.sleep(2)
