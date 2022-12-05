import time


class Timer:
    def __init__(self):
        self.event_time = None

    def start(self, duration):
        self.event_time = time.perf_counter() + duration

    def stop(self):
        self.event_time = None

    def is_expired(self):
        return True if self.event_time is not None and time.perf_counter() >= self.event_time else False

    def remaining(self):
        try:
            return max(self.event_time - time.perf_counter(), 0)
        except:
            return 0

    def is_run(self):
        return False if self.event_time is None else True

    def is_stop(self):
        return True if self.event_time is None else False

    def set_expired(self):
        self.event_time = 0


if __name__ == "__main__":

    tmr = Timer()
    tmr.start(5)
    while True:
        if tmr.is_run():
            print(tmr.remaining())
        if tmr.is_expired():
            print("TIMER")
            tmr.stop()
        time.sleep(1)
