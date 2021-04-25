# capscheduler
Scheduling Assistant for Civil Air Patrol Cadet Squadrons by Jonathan Madon <john@unwisegeek.net>

This is a scheduling assistant for Civil Air Patrol Cadet Squadrons based on Python and hopefully compatible across every system capable of running Python3.

Basic feature set is a work in progress.

Prerequisites
-------------

WSGI Server, but may be run locally for testing and basic use. See ./start bash file
Python 3 & Pip
Python VirtualEnv

Installation
------------

Clone this repository: git clone https://github.com/unwisegeek/capscheduler.git
Change into the directory: cd capscheduler
Create the virtual environment: virtualenv venv
Activate the virtual environment: source ./venv/bin/activate
Install the requirements: pip3 install -r requirements.txt
Create a secret key or move an existing secret key to the capscheduler directory: dd if=/dev/urandom bs=4096 count=100 | sha256sum > .secret_key
Copy sampleconfig.py to config.py and modify to suit your needs.
Create WSGI file (see example) to import capscheduler's app as application or run ./start