from bms import BMS



class BMS_DUMMY(BMS):
    def __init__(self, port, timeout):
        super().__init__()
        # optional (showed in ui but not used in control loop)
        self._pack_u = []
        self._pack_i = []
        self._pack_t = []
        self._pack_soc = []
        self._pack_cycle = []

    def update(self):
        # read data from BMS and set values
        # self._voltage = ...
        pass


    def get_state(self):
        return {
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
            # ...
        }

    def get_detail(self):
        return {
        }
