import random
import string
from bottle import request, response


class Session:
    """
    Simple sessionmanager for Bottle Webserver
    """
    def __init__(self, password, id_length=20):
        self.id_length = 20
        self.password = password
        self.sessions = []

    def login(self, password):
        if password == self.password:
            session_id = ''.join(random.choice(string.ascii_letters + string.digits) for i in range(self.id_length))
            if session_id not in self.sessions:
                self.sessions.append(session_id)
                self.sessions = self.sessions[-25:]  # limit to the latest 25 logins
            response.set_cookie('session', session_id, max_age=31556952 * 2)
            return True
        else:
            return False

    def is_valid(self, session_id):
        if session_id is None:
            # print("no session cookie set")
            return False
        elif session_id in self.sessions:
            # print("session is valid: {}".format(session_id))
            return True
        else:
            # print("invalid session: {}".format(session_id))
            return False
