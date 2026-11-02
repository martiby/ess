import os
import socket
import subprocess
import time

"""
Raspberry Pi health data for the web interface (/api/health)

CPU, temperature, throttling, RAM, network, disk usage and SD card info.
Rates (CPU %, network, SD writes) are calculated between two calls.
"""

SD_MANUFACTURER = {0x01: 'Panasonic', 0x02: 'Toshiba/Kingston', 0x03: 'SanDisk', 0x1b: 'Samsung', 0x1d: 'ADATA',
                   0x27: 'Phison', 0x28: 'Lexar', 0x31: 'Silicon Power', 0x41: 'Kingston', 0x74: 'Transcend',
                   0x76: 'Patriot', 0x82: 'Sony', 0x9f: 'Kingston'}

THROTTLED_BITS = {0: 'Unterspannung', 1: 'Takt begrenzt', 2: 'gedrosselt', 3: 'Temperaturgrenze',
                  16: 'Unterspannung seit Boot', 17: 'Takt begrenzt seit Boot', 18: 'gedrosselt seit Boot',
                  19: 'Temperaturgrenze seit Boot'}


def read(path, default=None):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return default


class Health:
    def __init__(self):
        self.last = None  # (time, cpu (idle, total), net {iface: (rx, tx)}, sd_write_sectors)
        self.sd_errors = None
        self.sd_errors_time = 0

    def cpu_times(self):
        v = [int(x) for x in read('/proc/stat').splitlines()[0].split()[1:]]
        idle = v[3] + v[4]  # idle + iowait
        return idle, sum(v[:8])

    def net_bytes(self):
        r = {}
        for line in read('/proc/net/dev', '').splitlines()[2:]:
            name, data = line.split(':', 1)
            name = name.strip()
            if name == 'lo':
                continue
            v = data.split()
            r[name] = (int(v[0]), int(v[8]))
        return r

    def sd_stat(self):
        v = read('/sys/block/mmcblk0/stat', '').split()
        return (int(v[2]), int(v[6])) if len(v) > 6 else (None, None)  # read / write sectors (512 byte)

    def throttled(self):
        try:
            out = subprocess.run(['/usr/bin/vcgencmd', 'get_throttled'], capture_output=True, text=True,
                                 timeout=2).stdout
            value = int(out.strip().split('=')[1], 16)
            return value, [name for bit, name in THROTTLED_BITS.items() if value & (1 << bit)]
        except Exception:
            return None, []

    def wifi_signal(self):
        for line in read('/proc/net/wireless', '').splitlines()[2:]:
            v = line.split()
            if v and v[0].startswith('wlan0'):
                try:
                    return int(float(v[3]))  # dBm
                except Exception:
                    return None
        return None

    def mmc_errors(self):
        """
        Count SD card error messages in the kernel log since boot (cached 5 minutes)
        """
        if time.time() - self.sd_errors_time > 300:
            self.sd_errors_time = time.time()
            try:
                out = subprocess.run(['dmesg'], capture_output=True, text=True, timeout=5).stdout
                self.sd_errors = sum(1 for line in out.splitlines()
                                     if 'mmc' in line and ('error' in line.lower() or 'timeout' in line.lower()))
            except Exception:
                self.sd_errors = None
        return self.sd_errors

    def root_readonly(self):
        """
        True if the root filesystem was remounted read only (typical after SD card errors)
        """
        for line in read('/proc/mounts', '').splitlines():
            v = line.split()
            if len(v) > 3 and v[1] == '/':
                return v[3].split(',')[0] == 'ro'
        return None

    def disk(self, path):
        try:
            s = os.statvfs(path)
            total = s.f_blocks * s.f_frsize
            free = s.f_bavail * s.f_frsize
            used = total - s.f_bfree * s.f_frsize
            return {'total_gb': round(total / 1e9, 1), 'used_gb': round(used / 1e9, 1),
                    'percent': round(used / (used + free) * 100) if used + free else None}
        except Exception:
            return None

    def get(self):
        t = time.time()
        cpu = self.cpu_times()
        net = self.net_bytes()
        sd_read, sd_write = self.sd_stat()

        d = {'hostname': socket.gethostname(), 'time': time.strftime('%Y-%m-%d %H:%M:%S')}

        # system
        uptime = float(read('/proc/uptime', '0').split()[0])
        d['uptime'] = '{}d {}h {}min'.format(int(uptime // 86400), int(uptime % 86400 // 3600), int(uptime % 3600 // 60))
        d['model'] = read('/proc/device-tree/model', '').replace('\x00', '')
        d['kernel'] = os.uname().release

        # cpu
        load = read('/proc/loadavg', '0 0 0').split()
        d['cpu_load'] = [float(x) for x in load[:3]]
        d['cpu_count'] = os.cpu_count()
        d['cpu_percent'] = None
        if self.last:
            di = cpu[0] - self.last[1][0]
            dt = cpu[1] - self.last[1][1]
            d['cpu_percent'] = round((1 - di / dt) * 100) if dt > 0 else None
        freq = read('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq')
        d['cpu_mhz'] = int(freq) // 1000 if freq else None
        temp = read('/sys/class/thermal/thermal_zone0/temp')
        d['cpu_temp'] = round(int(temp) / 1000, 1) if temp else None
        d['throttled'], d['throttled_info'] = self.throttled()

        # memory
        mem = {}
        for line in read('/proc/meminfo', '').splitlines():
            k, v = line.split(':')
            mem[k] = int(v.split()[0])  # kB
        total = mem.get('MemTotal', 0)
        used = total - mem.get('MemAvailable', 0)
        d['ram_total_mb'] = total // 1024
        d['ram_used_mb'] = used // 1024
        d['ram_percent'] = round(used / total * 100) if total else None
        d['swap_used_mb'] = (mem.get('SwapTotal', 0) - mem.get('SwapFree', 0)) // 1024
        d['ess_rss_mb'] = round(int(read('/proc/self/statm', '0 0').split()[1]) * os.sysconf('SC_PAGE_SIZE') / 1048576)

        # network
        d['net'] = []
        for name, (rx, tx) in net.items():
            n = {'name': name, 'state': read('/sys/class/net/{}/operstate'.format(name), '?'),
                 'rx_total_mb': round(rx / 1048576), 'tx_total_mb': round(tx / 1048576),
                 'rx_kbit': None, 'tx_kbit': None}
            if self.last and name in self.last[2] and t > self.last[0]:
                dt = t - self.last[0]
                n['rx_kbit'] = round((rx - self.last[2][name][0]) * 8 / 1000 / dt, 1)
                n['tx_kbit'] = round((tx - self.last[2][name][1]) * 8 / 1000 / dt, 1)
            speed = read('/sys/class/net/{}/speed'.format(name))
            n['speed_mbit'] = int(speed) if speed and speed.lstrip('-').isdigit() and int(speed) > 0 else None
            if name == 'wlan0':
                n['signal_dbm'] = self.wifi_signal()
            d['net'].append(n)

        # disk
        d['disk_root'] = self.disk('/')
        d['disk_boot'] = self.disk('/boot')

        # sd card (no SMART on SD cards: show identification, writes and kernel errors)
        dev = '/sys/block/mmcblk0/device/'
        manfid = read(dev + 'manfid')
        try:
            manufacturer = SD_MANUFACTURER.get(int(manfid, 16), manfid)
        except Exception:
            manufacturer = manfid
        sd = {'name': read(dev + 'name'), 'manufacturer': manufacturer, 'date': read(dev + 'date'),
              'size_gb': None, 'written_mb': None, 'write_mb_day': None, 'write_kb_s': None,
              'errors': self.mmc_errors(), 'readonly': self.root_readonly()}
        size = read('/sys/block/mmcblk0/size')
        if size:
            sd['size_gb'] = round(int(size) * 512 / 1e9, 1)
        if sd_write is not None:
            sd['written_mb'] = round(sd_write * 512 / 1048576)
            if uptime > 7200:  # average only meaningful some hours after boot (boot writes)
                sd['write_mb_day'] = round(sd_write * 512 / 1048576 / uptime * 86400)
            if self.last and self.last[3] is not None and t > self.last[0]:
                sd['write_kb_s'] = round((sd_write - self.last[3]) * 512 / 1024 / (t - self.last[0]), 1)
        life = read(dev + 'life_time')  # only eMMC
        if life:
            sd['life_time'] = life
        d['sd'] = sd

        self.last = (t, cpu, net, sd_write)
        return d


if __name__ == "__main__":
    import json

    h = Health()
    h.get()
    time.sleep(1)
    print(json.dumps(h.get(), indent=2))
