# 31.10.2026 Home Assistant webhook report in background thread

import json
import logging
import threading
import time
import urllib.request


class HaReport:
    """
    Send battery SOC and power to a Home Assistant webhook.

    Runs in its own thread, so an unreachable Home Assistant never blocks the ESS mainloop.
    Values are sent every 'interval' seconds, or earlier when SOC or power change significantly.
    """

    def __init__(self, url, interval=10, min_interval=2, power_delta=100, timeout=1, log_name='ha'):
        """
        :param url:          webhook url, empty or None disables reporting
        :param interval:     send at least every interval seconds
        :param min_interval: send not more often than every min_interval seconds
        :param power_delta:  power change in watts that triggers an early send
        :param timeout:      timeout in seconds for http request
        :param log_name:     name for logger
        """
        self.log = logging.getLogger(log_name)
        self.url = url
        self.interval = interval
        self.min_interval = min_interval
        self.power_delta = power_delta
        self.timeout = timeout
        self.lock = threading.Lock()
        self.soc = None
        self.power = None
        self.sent = None  # last sent (soc, power)
        self.t_sent = 0  # time of last send attempt
        self.online = True
        if self.url:
            threading.Thread(target=self.thread_send, daemon=True).start()
            self.log.info("start report thread url: {}".format(self.url))
        else:
            self.log.info("disabled, no url")

    def update(self, soc, power):
        """
        Store latest values, called from mainloop (non blocking)
        """
        with self.lock:
            self.soc = soc
            self.power = power

    def is_send_due(self, soc, power):
        t = time.perf_counter()
        if t - self.t_sent < self.min_interval:
            return False
        if self.sent is None or t - self.t_sent >= self.interval:
            return True
        return soc != self.sent[0] or abs(power - self.sent[1]) >= self.power_delta

    def thread_send(self):
        """
        Endless loop for threaded send
        """
        while True:
            with self.lock:
                soc, power = self.soc, self.power
            if soc is not None and self.is_send_due(soc, power):
                self.t_sent = time.perf_counter()
                self.send(soc, power)
            time.sleep(0.25)

    def send(self, soc, power):
        req = urllib.request.Request(self.url, data=json.dumps({"soc": soc, "power": power}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                response.read()
            self.sent = (soc, power)
            if not self.online:
                self.online = True
                self.log.info("home assistant reachable again")
        except Exception as e:
            if self.online:
                self.online = False
                self.log.warning("home assistant not reachable: {}".format(e))
