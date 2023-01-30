from abc import ABC, abstractmethod

"""
Interface class description of the BMS interface
"""


class BMS(ABC):

    def __init__(self):
        self._error = None  # None or string in case of an error
        self._voltage = None  # voltage [V]
        self._current = None  # current [A]
        self._temperature = None  # temperature [°C]
        self._soc = None  # State of charge [%]
        self._soc_low = None  # lowest soc with multiple packs (set to soc for single pack)
        self._soc_high = None  # highest soc with multiple packs (set to soc for single pack)

    @property
    def voltage(self):
        return self._voltage

    @property
    def current(self):
        return self._current

    @property
    def temperature(self):
        return self._temperature

    @property
    def soc(self):
        return self._soc

    @property
    def soc_low(self):
        return self._soc_low

    @property
    def soc_high(self):
        return self._soc_high

    @property
    def error(self):
        return self._error

    @abstractmethod
    def update(self):
        """
        Run update / read cycle. If implemented as thread, update() must be a Dummy
        :return:
        """
        pass

    @abstractmethod
    def get_state(self):
        """
        Get actual state

        :return: Dictionary
        """
        pass

    @abstractmethod
    def get_detail(self):
        """
        Get actual state with detailed Information

        :return: Dictionary
        """
        pass
