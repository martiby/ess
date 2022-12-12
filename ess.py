"""
ESS Starter
"""

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from app import App

os.makedirs('log', exist_ok=True)  # create paths if necessary


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[TimedRotatingFileHandler('log/log.txt', when='midnight'),
                              logging.StreamHandler()])

# specific logger configuration
# logging.getLogger('meterhub').setLevel(logging.DEBUG) # enable debug logging for a specific module

logging.getLogger('vebus').setLevel(logging.ERROR)
logging.getLogger('bms').setLevel(logging.ERROR)
# logging.getLogger('bms').setLevel(logging.DEBUG)
# logging.getLogger('bms').setLevel(logging.CRITICAL)
logging.getLogger('meterhub').setLevel(logging.ERROR)

app = App()
app.start()  # start application mainloop
