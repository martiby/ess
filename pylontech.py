import struct

"""
Pylontech / US2000 

Packet and Framehandling. See demo_pylontech.py for a simple example. 

30.11.2022  Martin Steppuhn     Split in pylontech.py (basic packets) and us2000.py (threaded service class)   
"""


def read_analog_value(com, address):
    """
    Read analog value (MAIN INFORMATION)

    TX: b'~20024642E00202FD33\r'
    RX: b'~20024600C06E10020F0C9A0C980C990C980C9A0C9A0C990C9B0C9C0C9A0C9B0C9B0C9B0C9B0C99050B740B550B570B530B630000BD06190F02C3500084E545\r'

    {'u_cell': (3226, 3224, 3225, 3224, 3226, 3226, 3225, 3227, 3228, 3226, 3227, 3227, 3227, 3227, 3225), 't': [20.1, 17.0, 17.2, 16.8, 18.4], 'q': 6415, 'q_total': 50000, 'cycle': 132, 'i': 0.0, 'u': 48.39, 'soc': 13}

    :param com: PySerial
    :param address: Address 0, ...
    :return: Dictionary with values
    """
    tx = encode_cmd(address + 2, 0x42, "{:02X}".format(address + 2).encode('utf-8'))
    # print("TX:", tx)
    com.reset_input_buffer()
    com.write(tx)

    rx = com.read_until(b'\r')
    # print("RX:", rx)
    frame = decode_frame(rx)
    if frame is not None:
        return parse_analog_value(frame)
    else:
        raise ValueError('receive failed dump={}'.format(rx))


def parse_analog_value(frame):
    """
    Parser for analog value packet

    :param frame: bytes
    :return: dictionary
    """
    d = {}
    p = 8
    cell_number = frame[p]  # US2000 = 15 Zellen
    d['u_cell'] = struct.unpack_from(">HHHHHHHHHHHHHHH", frame, p + 1)
    temp_number = frame[p + 31]
    temp = struct.unpack_from(">HHHHH", frame, p + 32)
    d['t'] = [(t - 2731) / 10 for t in temp]
    # Ampere, positive (charge), negative (discharge), with 100mA steps
    current, voltage, d['q'], d['q_total'], d['cycle'] = struct.unpack_from(">hHHxHH", frame, p + 42)
    d['i'] = current / 10
    d['u'] = voltage / 1000
    d['soc'] = round(100 * d['q'] / d['q_total'])
    return d


def read_serial_number(com, address):
    """
    Read serialnumber

    TX: b'~20024693E00202FD2D\r'
    RX: b'~20024600C0220248505443523033313731313132353930F6D2\r'    {'serial': 'HPTCR03171112590'}

    TX: b'~20034693E00203FD2B\r'
    RX: b'~20034600C0220348505442483032323430413031323335F6D5\r'    {'serial': 'HPTBH02240A01235'}

    :param com: PySerial
    :param address: Address 0, ...
    :return: Dictionary with serial
    """
    tx = encode_cmd(address + 2, 0x93, "{:02X}".format(address + 2).encode('utf-8'))
    # print(tx)
    com.write(tx)  # send command to battery
    com.reset_input_buffer()  # clear receive buffer
    rx = com.read_until(b'\r')  # read
    # print(rx)
    frame = decode_frame(rx)  # check if valid frame
    if frame is not None:
        return {'serial': frame[7:7 + 16].rstrip(b'\x00').decode("utf-8")}
    else:
        raise ValueError('receive failed dump={}'.format(rx))


def read_alarm_info(com, address):
    """
    Read alarm status from a pack

    Pack 0:
    TX: b'~20024644E00202FD31\r'
    RX: b'~20024600A04210020F000000000000000000000000000000050000000000000000000E00000000F108\r'
    0 {'u_cell': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 't': [0, 0, 0, 0, 0], 'i_chg': 0, 'u_pack': 0, 'i_dis': 0, 'status': [0, 14, 0, 0, 0], 'ready': True}

    Pack 1:
    TX: b'~20034644E00203FD2F\r'
    RX: b'~20034600A04210030F000000000000000000000000000000050000000000000000000E00000000F106\r'
    1 {'u_cell': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 't': [0, 0, 0, 0, 0], 'i_chg': 0, 'u_pack': 0, 'i_dis': 0, 'status': [0, 14, 0, 0, 0], 'ready': True}

    :param com: PySerial
    :param address: Address 0, ...
    :return: Dictionary with values
    """
    tx = encode_cmd(address + 2, 0x44, "{:02X}".format(address + 2).encode('utf-8'))
    # print("TX:", tx)
    com.reset_input_buffer()
    com.write(tx)

    rx = com.read_until(b'\r')
    # print("RX:", rx)
    frame = decode_frame(rx)
    if frame is not None:
        return parse_alarm_info(frame)
    else:
        raise ValueError('receive failed dump={}'.format(rx))


def parse_alarm_info(frame):
    """
    Parser for alarm info packet

    :param frame: bytes
    :return: dictionary, 'ready'=True --> READY,  if 'error' is set --> FAILURE
    """
    d = {}
    p = 8
    cell_number = frame[p]  # US2000 = 15 Zellen
    d['u_cell'] = list(frame[p + 1:p + 1 + cell_number])  # bytes to list
    p = p + 1 + cell_number
    temp_number = frame[p]
    d['t'] = list(frame[p + 1:p + 1 + temp_number])
    p = p + 1 + temp_number
    d['i_chg'], d['u_pack'], d['i_dis'] = struct.unpack_from(">BBB", frame, p)
    p += 3
    d['status'] = list(frame[p:p + 5])  # bytes to list
    d['ready'] = True if (d['status'][1] & 0x04) else False
    if d['status'][0]:
        d['error'] = True
    return d


def read_manufacturer_info(com, address):
    """
    Get manufacturer information

    ACHTUNG!!!

    Bei der Abfrage von zwei verschiedenen Akkus über die Adresse 2 und 3 wird immer die selbe Information geliefert !!!

    TX: b'~200246510000FDAC\r'
    RX: b'~20024600C04055533230303043000000010750796C6F6E2D2D2D2D2D2D2D2D2D2D2D2D2D2D2DEFBD\r'
    {'device': 'US2000C', 'version': '1.7', 'manufacturer': 'Pylon'}

    TX: b'~200346510000FDAB\r'
    RX: b'~20034600C04055533230303043000000010750796C6F6E2D2D2D2D2D2D2D2D2D2D2D2D2D2D2DEFBC\r'
    {'device': 'US2000C', 'version': '1.7', 'manufacturer': 'Pylon'}


    Bei einer Einzelabfrage des zweiten System kommt die richtige Information !!!

    TX: b'~200246510000FDAC\r'
    RX: b'~20024600C0405553324B42504C000000020450796C6F6E2D2D2D2D2D2D2D2D2D2D2D2D2D2D2DEF97\r'
    {'device': 'US2KBPL', 'version': '2.4', 'manufacturer': 'Pylon'}

    ===> Im Verbudn über den Link nicht zu gebrauchen
    """

    tx = encode_cmd(address + 2, 0x51)
    print('TX:', tx)
    com.write(tx)  # send command to battery
    com.reset_input_buffer()  # clear receive buffer
    rx = com.read_until(b'\r')  # read
    print('RX:', rx)
    rx_frame = decode_frame(rx)  # check if valid frame
    if rx_frame is not None:
        d = {}
        d['device'] = rx_frame[6:16].rstrip(b'\x00').decode("utf-8")
        d['version'] = "{}.{}".format(rx_frame[16], rx_frame[17])
        d['manufacturer'] = rx_frame[18:38].rstrip(b'-').decode("utf-8")
        return d
    else:
        raise ValueError('receive failed dump={}'.format(rx))


# ====== Helpers ======

def get_frame_checksum(frame):
    """
    Calculate checksum for a given frame

    :param frame: ascii hex frame
    :return: checksum as interger
    """
    checksum = 0
    for b in frame:
        checksum += b
    checksum = ~checksum
    checksum %= 0x10000
    checksum += 1
    return checksum


def get_info_length(info):
    """
    Build length code for information field

    :param info: information field
    :return: length code
    """
    lenid = len(info)  # length
    if lenid == 0:
        return 0
    li = (lenid & 0xf) + ((lenid >> 4) & 0xf) + ((lenid >> 8) & 0xf)
    li = li % 16
    li = 0b1111 - li + 1
    return (li << 12) + lenid


def encode_cmd(addr, cid2, info=b''):
    """
    Encode command frame

    Example:    b'\x7E20024642E00202FD33\x0D'     \x7E 20 02 46 42 E0 02 02 FD 33 \x0D
                20      Version
                02      Address
                46      CID1
                42      CID2
                E0 02   Length
                02      Info (Command info), Address to read, RS485 Address starts at 2
                FD 33   Checksum

    :param addr: address
    :param cid2: cid2 code
    :param info: additional parameter (called information)
    :return: frame
    """
    cid1 = 0x46
    info_length = get_info_length(info)
    inner_frame = "{:02X}{:02X}{:02X}{:02X}{:04X}".format(0x20, addr, cid1, cid2, info_length).encode()
    inner_frame += info
    checksum = get_frame_checksum(inner_frame)
    frame = (b"~" + inner_frame + "{:04X}".format(checksum).encode() + b"\r")

    return frame


def decode_frame(raw_frame):
    """
    Decode received frame, checksum is validated

    :param raw_frame: Raw ASCII Hex frame
    :return: frame in bytes
    """
    if len(raw_frame) >= 18 and raw_frame[0] == ord('~') and raw_frame[-1] == ord('\r') and len(raw_frame) % 2 == 0:
        frame_chk = int(raw_frame[-5:-1], 16)  # hex encoded checksum from received frame
        calc_chk = get_frame_checksum(raw_frame[1:-5])  # calculated checksum from data
        # print(frame_chk, calc_chk)
        if frame_chk == calc_chk:
            frame = bytes.fromhex(raw_frame[1:-1].decode("utf-8"))  # hex --> bytes
            return frame
    return None
