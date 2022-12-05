# 13.10.2022 Martin Steppuhn

class FSM:
    """
    Minimal FSM Framework. Could be used as baseclass to provide statemachine functionality.
    Init must be called with: super().__init__('****')

    set_fsm_state(state)
    run_fsm()
    """

    def __init__(self, state):
        """
        Init
        """
        self._fsm_state = state  # actual state, string with suffix 'state1' --> self.fsm_state1
        self._fsm_next_state = state  # next state, string with suffix 'state1' --> self.fsm_state1

    def run_fsm(self):
        """
        Run statemachine
        """
        if self._fsm_next_state:
            entry = True  # set entry flag for first run in new state
            self._fsm_state = self._fsm_next_state
            self._fsm_next_state = None
        else:
            entry = False

        try:
            getattr(self, "fsm_" + self._fsm_state)(entry)
        except:
            self.log.exception("fsm call exception: {}".format(self._fsm_state))

    def set_fsm_state(self, state):
        """
        Switch state

        :param state:  string with suffix 'state1' --> self.fsm_state1
        """
        self._fsm_next_state = state
