import json
import logging
import os
import threading

import bottle
from bottle import Bottle, request, response, static_file, redirect, template

from config import config
from session import Session
from utils import dictget
from version import __version__

bottle.TEMPLATE_PATH = [config['www_path']]  # must be a list !!!


class AppWeb:
    """
    Webserverintegration for application
    """

    def __init__(self, app, log='web'):
        self.app = app  # reference to application
        self.log = logging.getLogger(log)
        self.web = Bottle()  # webserver

        self.session = Session(password=config['password'])

        self.manual_session = None  # session of the client which has manual control

        # setup routes
        self.web.route('/', callback=self.web_index)  # hosting static files
        self.web.route('/login', callback=self.web_login, method=('GET', 'POST'))  # application state in json format
        self.web.route('/api/state', callback=self.web_api_state, method=('GET', 'POST'))
        self.web.route('/api/state/<state>', callback=self.web_api_state)
        self.web.route('/api/set', callback=self.web_api_set, method=('GET', 'POST'))
        self.web.route('/api/bms', callback=self.web_api_bms)  # full bms data in json format
        self.web.route('/log', callback=self.web_log)  # access to logfile
        self.web.route('/chart', callback=self.web_chart)  #
        self.web.route('/blackbox', callback=lambda : "\n".join(self.app.blackbox.record_lines))  #
        self.web.route('/<filepath:path>', callback=self.web_static)  # hosting static files

        logging.getLogger('waitress.queue').setLevel(logging.ERROR)  # hide waitress info log
        # start webserver thread
        threading.Thread(target=self.web.run, daemon=True,
                         kwargs=dict(host='0.0.0.0', port=8888, server='waitress')).start()

    def web_login(self):
        """
        Login view
        :return:
        """
        password = request.forms.get("password", default=None)
        remote_addr = request.environ.get('REMOTE_ADDR')
        if password is None:
            self.log.info("login form request from {}".format(remote_addr))
        elif self.session.login(password):
            self.log.info("login from {} successful, redirect to /".format(remote_addr))
            redirect('/')
            return
        else:
            self.log.error("login attempt from {} with invalid password: {}".format(remote_addr, password))
        return static_file('login.html', root=config['www_path'])

    def web_index(self, filepath='index.html'):
        """
        Webserver interface for static files
        """
        session_id = request.get_cookie('session')
        remote_addr = request.environ.get('REMOTE_ADDR')

        if self.session.is_valid(session_id):  # static files only after login (session)
            self.log.debug(
                "request to: {} from: {} with valid session_id: {}".format(filepath, remote_addr, session_id))

            bottle.TEMPLATES.clear()  # DEBUG !!!!

            # https://pwp.stevecassidy.net/bottle/templating/

            d = {
                "version": __version__,
                "bms_cfg": range(config['us2000_pack_number']),
                "enable_car": config['enable_car'],
                "enable_heat": config['enable_heat'],
                "setting": [s['name'] for s in config['setting']]
            }
            return template('index.html', d)
            # return static_file('index.html', root=self.app.www_path)
        else:
            if session_id:
                self.log.info(
                    "index request from:{} unknown session_id: {}, redirect to /login".format(remote_addr, session_id))
            else:
                self.log.info(
                    "index request from:{} without session_id, redirect to /login".format(filepath, remote_addr))
            redirect('/login')

    def web_static(self, filepath=None):
        """
        Webserver interface for static files
        """
        if filepath == 'index.html':
            self.web_index()
        else:
            return static_file(filepath, root=self.app.www_path)

    def web_log(self):
        """
        /log    Webserver interface to access the logfile
        """
        response.content_type = 'text/plain'
        return open(os.path.join('log', 'log.txt'), 'r').read()

    def web_api_state(self):
        """
        /api/state      Webserver interface to get application state in JSON
        """

        try:
            post = json.loads(request.body.read())  # manual_set_p
            self.app.ui_command = post
            # print("web post ui_command", post)
        except:
            pass

        session_id = request.get_cookie('session')

        state = self.app.get_state()

        # manual auth
        if self.app.mode == 'manual' and self.manual_session and session_id == self.manual_session:
            state['manual_auth'] = True

        # valid session
        if not self.session.is_valid(session_id):
            state['session_invalid'] = True

        return state

    def web_api_set(self):
        """
        /api/set      Webserver interface to set by JSON
        """
        session_id = request.get_cookie('session')

        if self.session.is_valid(session_id):
            try:
                post = json.loads(request.body.read())  # manual_set_p
                self.log.info("/api/set {}".format(post))

                if 'option' in post:
                    self.app.setting = int(post['option'])

                if 'mode' in post and post['mode'] in ('off', 'auto', 'manual'):
                    self.app.mode = post['mode']
                    self.app.charge_start_timer.set_expired()  # trigger
                    self.app.feed_start_timer.set_expired()  # trigger

                    if post['mode'] == 'manual':
                        self.manual_session = session_id
                        self.log.info('manual control for session: {} started'.format(session_id))
                    else:
                        self.manual_session = None

                if 'reset_error' in post and post['reset_error'] is True:  # init = Error reset
                    self.log.info("manual error reset !")
                    self.app.set_fsm_state('init')

            except Exception as e:
                self.log.error('/api/set exception: {}'.format(e))
        else:
            self.log.error('/api/set without valid session')
        return self.app.get_state()

    def web_api_bms(self):
        """
        /api/state      Webserver interface to get full bms info as json
        """
        response.content_type = 'application/json'
        return json.dumps(self.app.bms.data_detail)

    def web_chart(self):
        """

        """
        # chart = self.app.trace.get_chart([('home', ('meterhub', 'home_all_p')), ('grid', ('meterhub', 'grid_p')), ('grid', ('meterhub', 'car_p'))])

        chart = {'x': [], 'home': [], 'grid': [], 'bat_feed': [], 'bat_charge': [], 'charge_set': [], 'feed_set': []}

        i = 0
        for t in self.app.trace.buffer:

            grid = dictget(t, ('meterhub', 'grid_p'))
            bat = dictget(t, ('meterhub', 'bat_p'))
            home_all = dictget(t, ('meterhub', 'home_all_p'))
            car = dictget(t, ('meterhub', 'car_p'))
            home = home_all - car

            set_p = dictget(t, ('ess', 'set_p'))
            try:
                charge_set = max(set_p, 0)
                feed_set = max(-set_p, 0)
            except:
                charge_set = None
                feed_set = None

            chart['home'].append(home)
            chart['grid'].append(grid)

            chart['bat_charge'].append(bat if bat and bat > 0 else 0)
            chart['bat_feed'].append(-bat if bat and bat < 0 else 0)
            chart['charge_set'].append(charge_set)
            chart['feed_set'].append(feed_set)

            chart['x'].append(i)
            i += 1

        response.content_type = 'application/javascript'
        return "var chart =" + json.dumps(chart)
