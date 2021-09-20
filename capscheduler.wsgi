#!/usr/bin/python3
import logging
import sys

logging.basicConfig(stream=sys.stderr)
sys.path.insert(0, "/var/www/capscheduler/")

python_home = "/var/www/capscheduler/venv"

activate_this = python_home + "/bin/activate_this.py"
with open(activate_this) as file_:
    exec(file_.read(), dict(__file__=activate_this))

from capscheduler import app as application
