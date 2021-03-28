import os, hashlib, secrets, string
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, session
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_script import Server, Manager
from flask_migrate import Migrate, MigrateCommand

from config import *

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///capscheduler.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Check for secret_key file.
if not os.path.exists('./.secret_key'):
    raise Exception('Please generate a secret key.\r\nEx: dd if=/dev/random bs=100M count=1 | sha256sum | cut -d ' ' -f1 > .secret_key')
else:
    app.config['SECRET_KEY'] = open('./.secret_key', 'r').read().encode('utf8')

# Configure Server-side sessions
app.config['SESSION_TYPE'] = 'null'
# app.config['SESSION_USE_SIGNER'] = True
sess = Session()


# Configure database migratiosn
migrate = Migrate(app, db)
manager = Manager(app)

manager.add_command('db', MigrateCommand)
manager.add_command('runserver', Server(host='0.0.0.0', port=5000,use_debugger=True,use_reloader=True))

def result_length(set):
    counter = 0
    while True:
        try:
            a = set[counter].eventId
            counter += 1
        except:
            break
    return counter

def convert_bool_to_ballot(targValue):
    if targValue == 1:
        return "&#9744"
    else:
        return "&#9745"

def convert_times_to_minutes(stopTime, startTime, format="%H:%M"):
    difference = (datetime.strptime(stopTime, format) - datetime.strptime(startTime, format))
    minutes = difference.total_seconds() // 60
    return int(minutes)

def count_stats(year, month, acct, mins):
    """
    Adds contact hours to stats db
    
    Requires: year, month, acct, mins
    """
    try:
        statsobj = MonthlyStats.query.filter_by(statsYear=int(year)).filter_by(statsMonth=int(month)).filter_by(contactAccount=acct)
        statsobj[0].contactMinutes = statsobj[0].contactMinutes + mins
    except:
        newstat = MonthlyStats(statsYear=int(year),statsMonth=int(month),contactAccount=acct,contactMinutes=int(mins))
        db.session.add(newstat)
    db.session.commit()
    return
    
def uncount_stats(year, month, acct, mins):
    """
    Removes contact hours from stats db
    
    Requires: year, month, acct, mins
    """
    try:
        statsobj = MonthlyStats.query.filter_by(statsYear=int(year)).filter_by(statsMonth=int(month)).filter_by(contactAccount=acct)
        statsobj[0].contactMinutes = statsobj[0].contactMinutes - mins
        db.session.commit()
    except:
        pass
    return


# Create the event model for the database.
class Event(db.Model):
    __tablename__ = 'events'
    __table_args__ = { 'sqlite_autoincrement': True }
    eventId = db.Column(db.Integer, primary_key=True)
    eventDate = db.Column(db.String(10), unique=False, nullable=False)
    startTime = db.Column(db.String(5), unique=False, nullable=False)
    stopTime = db.Column(db.String(5), unique=False, nullable=False)
    eventName = db.Column(db.String(80), unique=False, nullable=False)
    eventLdr = db.Column(db.String(80), unique=False, nullable=False)
    contactAccount = db.Column(db.String(20), unique=False, nullable=False)
    contactMinutes = db.Column(db.Integer, unique=False, nullable=False)
    isAgreedTo = db.Column(db.Integer, unique=False, nullable=False, server_default="0")
    isEmailScheduled = db.Column(db.Integer, unique=False, nullable=False, server_default="0")
    isEmailSent = db.Column(db.Integer, unique=False, nullable=False, server_default="0")
    isEmailConfirmed = db.Column(db.Integer, unique=False, nullable=False, server_default="0")
    isEmailThanked = db.Column(db.Integer, unique=False, nullable=False, server_default="0")
    isDeleted = db.Column(db.Integer, unique=False, nullable=False, server_default="0")
    isStated = db.Column(db.Integer, unique=False, nullable=False, server_default="0")

class MonthlyStats(db.Model):
    __tablename__ = 'monthly-statistics'
    __table_args__ = { 'sqlite_autoincrement': True }
    statsId = db.Column(db.Integer, primary_key=True)
    statsYear = db.Column(db.Integer, unique=False, nullable=False)
    statsMonth = db.Column(db.Integer, unique=False, nullable=False)
    contactAccount = db.Column(db.String(30), unique=False, nullable=False)
    contactMinutes = db.Column(db.Integer, unique=False, nullable=False)
    
class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = { 'sqlite_autoincrement': True }
    userId = db.Column(db.Integer, primary_key=True )
    userFirstName = db.Column(db.String(30), unique=False, nullable=False )
    userLastName = db.Column(db.String(30), unique=False, nullable=False )
    userOrg = db.Column(db.String(30), unique=False, nullable=True )
    userRank = db.Column(db.String(30), unique=False, nullable=False )
    userEmail = db.Column(db.String(50), unique=True, nullable=False )
    userPass = db.Column(db.String(128), unique=True, nullable=False )
    user2FAEnabled = db.Column(db.Integer, unique=False, nullable=False, server_default = "0" )
    user2FAKey = db.Column(db.String(32), unique=True, nullable=True, server_default = "" )
    userLoginFails = db.Column(db.Integer, unique=False, nullable=False, server_default = "0" )
    userLoginLock = db.Column(db.Integer, unique=False, nullable=False, server_default = "0" )
    userPermissions = db.Column(db.String(128), unique=False, nullable=False, server_default = "viewer" )

# Initialize the database file if one does not exist.
if not os.path.exists('./capscheduler.db'):
    print('Creating database.')
    db.create_all()

@app.route('/', methods=['GET', 'POST'])
def index():
    # Get GET variables and come back with them in a session.
    keylist = []
    for each in request.values.keys():
        keylist += [ each ]
    
    if len(keylist) > 0:
        for each in request.values.keys():
            session[each] = request.values.get(each)
        return redirect('/')

    pageStatus = session.get('status', '')
    if not session.get('userId', False):
        status = session.get('status', '')
        session.clear()
        return render_template('login.html', status=pageStatus)
    # If the user arrives at the index page witho7ut a date, pick today.
    if 'meetingDate' in request.values or session.get('meetingDate', '-1') != '-1': # Date exists in POST or GET
        meetingDate = session.get('meetingDate', '-1')
        if meetingDate == '-1':
            meetingDate = request.values.get('meetingDate')
            session['meetingDate'] = meetingDate
            return redirect('/schedule')
        return redirect('/schedule')
    else: # Pick the next day that coincides with the meeting day.
        nextMeetingDay = date.today()
        while nextMeetingDay.weekday() != DAYNUM[meetingDay]:
            nextMeetingDay += timedelta(1)
        meetingDate = nextMeetingDay.strftime(DATEFMT)
        session['meetingDate'] = meetingDate
        return redirect('/schedule')

@app.route('/schedule', methods=['GET', 'POST'])
def schedule_window():
    # If we get GET or POST variables, convert them to session data:
    #session.clear()
    
    keylist = []
    for each in request.values.keys():
        keylist += [ each ]
    
    if len(keylist) > 0:
        for each in request.values.keys():
            session[each] = request.values.get(each)
        return redirect('/schedule') # Come back with all GET variables converted to session

    pageStatus = session.get('status', '')
    pageAction = session.get('pageAction', '')
    id = session.get('eventId', -99)

    # Grab variabes for user data
    userId = session.get('userId', False)
    userData = []
    if not userId:
        return redirect('/')
    else:
        userobj = User.query.filter_by(userId=userId)
        userData += [ userobj[0].userRank ]
        userData += [ userobj[0].userFirstName ]
        userData += [ userobj[0].userLastName ]
        userData += [ userobj[0].userOrg ]
        userData += [ userobj[0].userPermissions ]

    # Grab variables for 'edit' pageAction
    eventData = []
    if pageAction == 'EditEvent':
        eventobj = Event.query.filter_by(eventId=int(id))
        eventData += [ eventobj[0].eventId ]
        eventData += [ eventobj[0].eventDate ]
        eventData += [ eventobj[0].startTime ]
        eventData += [ eventobj[0].stopTime ]
        eventData += [ eventobj[0].eventName ]
        eventData += [ eventobj[0].eventLdr ]
        eventData += [ CONTACT_ABRVS[eventobj[0].contactAccount] ]
        eventData += [ eventobj[0].isAgreedTo ]
        eventData += [ eventobj[0].isEmailScheduled ]
        eventData += [ eventobj[0].isEmailSent ]
        eventData += [ eventobj[0].isEmailConfirmed ]
        eventData += [ eventobj[0].isEmailThanked ]

    if session.get('meetingDate', '-1') != "-1":
        meetingDate = session.get('meetingDate', '-1')
        
        # Account for meetingDate coming back in a different format
        if meetingDate[3] == '-': # Month First
            meetingDate = datetime.strptime(meetingDate, DATEFMT)
        else: # Year First
            meetingDate = datetime.strptime(meetingDate, '%Y-%m-%d')

        prevDate = meetingDate + timedelta(-7)
        prevDate = prevDate.strftime(DATEFMT)
        nextDate = meetingDate + timedelta(+7)
        nextDate = nextDate.strftime(DATEFMT)
        meetingDate = meetingDate.strftime('%Y-%m-%d')

        # Get results from DB
        queryResults = Event.query.filter_by(eventDate=meetingDate).order_by(Event.startTime)
        date = meetingDate.split('-')
        sortedQueryResults = []
        minutes = {}
        monthly_minutes = []

        # Populate minutes and monthly_minutes
        for account in CONTACT_ACCOUNTS:
            minutes[CONTACT_ABRVS[account]] = 0
            queryStats = MonthlyStats.query.filter_by(statsYear=int(date[0])) \
                                       .filter_by(statsMonth=int(date[1])) \
                                       .filter_by(contactAccount=account)
            try:
                monthly_minutes += [ queryStats[0].contactMinutes ]
            except:
                monthly_minutes += [ 0 ]
        
        counter = result_length(queryResults)
        for i in range(0, counter):
            if queryResults[i].isDeleted != 1:
                minutes[CONTACT_ABRVS[queryResults[i].contactAccount]] += queryResults[i].contactMinutes
                row = '{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}'.format(queryResults[i].eventId, queryResults[i].eventDate, queryResults[i].startTime, \
                                                             queryResults[i].stopTime, queryResults[i].eventName, queryResults[i].eventLdr, \
                                                             CONTACT_ABRVS[queryResults[i].contactAccount], queryResults[i].isAgreedTo, \
                                                             queryResults[i].isEmailScheduled, queryResults[i].isEmailSent, queryResults[i].isEmailConfirmed, \
                                                             queryResults[i].isEmailThanked)
                sortedQueryResults += [ row.split('|') ]
        
        # Convert minute and abrvs dictionaries to lists before sending them:
        minute_list = list(minutes.values())
        abrvs_list = list(CONTACT_ABRVS.values())
        return render_template('index.html', meetingDate=meetingDate, prevDate=prevDate, nextDate=nextDate, results=sortedQueryResults, status=pageStatus,
                                pageAction=pageAction, eventData=eventData, accounts=CONTACT_ACCOUNTS, minutes=minute_list, 
                                mminutes=monthly_minutes, abrvs=abrvs_list, eventId=id, session=session, userData=userData)
    else:
        # Redirect if the date has not been set.
        return redirect('/')

@app.route('/newevent', methods=['GET', 'POST'])
def newevent():
    def isin(flag):
        if flag in request.values:
            return  1
        else:
            return 0
    
    def abrv_to_acct(abrv):
        for each in CONTACT_ACCOUNTS:
            if CONTACT_ABRVS[each] == abrv:
                return each
        else:
            raise Exception("Unknown contact hour abbreviation provided.")
    
    # Check that all required variables that are needed to create an event in the database are there.
    reqVarsExist = True
    meetingDate = request.values.get('meetingDate')
    for each in [ 'eventDate', 'startTime', 'stopTime', 'eventName', 'eventLdr', 'contactAccount' ]:
        if each not in request.values:
            reqVarsExist = False
    if reqVarsExist:
        # Create list of variable values.
        data = []
        for each in [ 'eventDate', 'startTime', 'stopTime', 'eventName', 'eventLdr', 'contactAccount' ]:
            if each == 'contactAccount':
                data += [ abrv_to_acct(request.values.get(each)) ]
            else:
                data += [ request.values.get(each) ]
            
        # Calculate contact minutes for new events.
        data += [ convert_times_to_minutes(data[2], data[1]) ]

        for each in [ 'isAgreedTo', 'isEmailScheduled', 'isEmailSent', 'isEmailConfirmed', 'isEmailThanked' ]:
            data += [ isin(each) ]

        # Create a new DB entry.
        newevent = Event(eventDate=data[0], startTime=data[1], stopTime=data[2], eventName=data[3], eventLdr=data[4], \
                         contactAccount=data[5], contactMinutes=data[6], isAgreedTo=data[7], isEmailScheduled=data[8], \
                         isEmailSent=data[9], isEmailConfirmed=data[10], isEmailThanked=data[11], isDeleted=0)
        # Commit the DB entry and send them back to the index page with the previous date.
        db.session.add(newevent)
        db.session.commit()
        newevent = ''
        # Add to statistics DB
        date = data[0].split('-')
        count_stats(date[0], date[1], data[5], data[6])
        # Clear session variables that no longer need to be there
        try: 
            session.pop('pageAction')
        except:
            pass
        try:
            session.pop('eventId')
        except:
            pass
        # Redirect
        return redirect('/schedule?meetingDate={}&status=Event%20Added'.format(meetingDate))
    return redirect('/schedule?meetingDate={}&status=Error%20Adding%20Event'.format(meetingDate))

@app.route('/delete', methods=['GET', 'POST'])
def deleteevent():
    meetingDate = request.values.get('meetingDate')
    id = request.values.get('eventId')
    eventobj = Event.query.filter_by(eventId=int(id)).first()
    eventobj.isDeleted = 1
    date = eventobj.eventDate.split('-')
    uncount_stats(date[0], date[1], eventobj.contactAccount, eventobj.contactMinutes)
    db.session.commit()
    status = 'Event Deleted'
    return redirect('/schedule?meetingDate={}&status={}'.format(meetingDate, status))

@app.route('/edit', methods=['POST'])
def editevent():
    def isin(flag):
        if flag in request.values:
            return request.values.get(flag)
        else:
            return 0

    def abrv_to_acct(abrv):
        for each in CONTACT_ACCOUNTS:
            if CONTACT_ABRVS[each] == abrv:
                return each
        else:
            raise Exception("Unknown contact hour abbreviation provided.")

    meetingDate = request.values.get('meetingDate')
    id = request.values.get('eventId')
    status = "Event Updated"
    event = Event.query.filter_by(eventId=int(id)).first()
    event.eventDate = request.values.get('eventDate')
    event.startTime = request.values.get('startTime')
    event.stopTime = request.values.get('stopTime')
    event.eventName = request.values.get('eventName')
    event.eventLdr = request.values.get('eventLdr')
    event.contactAccount = abrv_to_acct(request.values.get('contactAccount'))

    # Calculate new contact hours.

    event.contactMinutes = convert_times_to_minutes(request.values.get('stopTime'), request.values.get('startTime'))

    event.isAgreedTo = isin('isAgreedTo')
    event.isEmailScheduled = isin('isEmailScheduled')
    event.isEmailSent = isin('isEmailSent')
    event.isEmailConfirmed = isin('isEmailConfirmed')
    event.isEmailThanked = isin('isEmailThanked')
    event.isEmailDeleted = isin('isDeleted')
    db.session.commit()
    try: 
        session.pop('pageAction')
    except:
        pass
    try:
        session.pop('eventId')
    except:
        pass
    return redirect('/schedule?meetingDate={}&status={}'.format(meetingDate, status))

@app.route('/recalculatestats', methods=['GET', 'POST'])
def recalcstats():
    meetingDate = request.values.get('meetingDate')
    eventQuery = Event.query
    statsobj = MonthlyStats.query.delete()
  
    for i in range(0, result_length(eventQuery)):
        if eventQuery[i].isDeleted != 1:
            date = eventQuery[i].eventDate.split('-')
            count_stats(date[0], date[1], eventQuery[i].contactAccount, eventQuery[i].contactMinutes) # year, month, acct, mins
            eventQuery[i].isStated = 1
            db.session.commit()
    return redirect('/schedule?meetingDate={}&status=Stats Recalculated'.format(meetingDate))

@app.route('/login', methods=['GET', 'POST'])
def login():
    foundUser = False
    LOGIN_ERROR_REDIRECT = '/?status=Error has occurred. Please try again.'
    try:
        userName = request.values.get('userName')
        userPass = request.values.get('userPass')
    except:
        userName = False
        userPass = False

    if userName != False and userPass != False:
        userobj = User.query.filter_by(userEmail=userName)
        try:
            testVariable = userobj[0].userId
        except:
            return redirect(LOGIN_ERROR_REDIRECT)
        salt = userobj[0].userPass[64:96]
        passhash = userobj[0].userPass[0:64]

        hashobj = hashlib.sha3_256()
        hashobj.update(salt.encode('utf-8') + userPass.encode('utf-8'))

        servhash = hashobj.hexdigest()

        passed = False
        if passhash == servhash:
            passed = True
            hashobj = ""
            salt = ""
            passhash = ""
            servhash = ""
        
        if passed:
            session['userId'] = userobj[0].userId
            return redirect('/')
        return redirect(LOGIN_ERROR_REDIRECT)
    else:
        session.clear()
        return redirect(LOGIN_ERROR_REDIRECT)


@app.route('/logout', methods=['GET'])
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    #app.run(debug=True, host='0.0.0.0')
    manager.run()

