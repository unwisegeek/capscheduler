import os
from flask import Flask, render_template, request, redirect
from datetime import datetime, date, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_script import Server, Manager
from flask_migrate import Migrate, MigrateCommand

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///capscheduler.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

migrate = Migrate(app, db)
manager = Manager(app)

manager.add_command('db', MigrateCommand)
manager.add_command('runserver', Server(host='0.0.0.0', port=5000,use_debugger=True,use_reloader=True))

DAYNUM = { 'Monday': 0,
               'Tuesday': 1,
               'Wednesday': 2,
               'Thursday': 3,
               'Friday': 4,
               'Saturday': 5,
               'Sunday': 6,
}

CONTACT_ACCOUNTS = [
    'None',
    'Aerospace',
    'Character Development',
    'Emergency Services',
    'Leadership',
    'Physical Training',
    'Safety'
]

CONTACT_ABRVS = {
    'None': 'NA',
    'Aerospace': 'AE',
    'Character Development': 'CD',
    'Emergency Services': 'ES',
    'Leadership': 'LD',
    'Physical Training': 'PT',
    'Safety': 'SF'
}

DATEFMT = '%Y-%m-%d'
meetingDay = 'Thursday'

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
    isAgreedTo = db.Column(db.Integer, unique=False, nullable=False)
    isEmailScheduled = db.Column(db.Integer, unique=False, nullable=False)
    isEmailSent = db.Column(db.Integer, unique=False, nullable=False)
    isEmailConfirmed = db.Column(db.Integer, unique=False, nullable=False)
    isDeleted = db.Column(db.Integer, unique=False, nullable=False)
    isStated = db.Column(db.Integer, unique=False, nullable=False, default=0)

class MonthlyStats(db.Model):
    __tablename__ = 'monthly-statistics'
    __table_args__ = { 'sqlite_autoincrement': True }
    statsId = db.Column(db.Integer, primary_key=True)
    statsYear = db.Column(db.Integer, unique=False, nullable=False)
    statsMonth = db.Column(db.Integer, unique=False, nullable=False)
    contactAccount = db.Column(db.String(30), unique=False, nullable=False)
    contactMinutes = db.Column(db.Integer, unique=False, nullable=False)
    
    

# Initialize the database file if one does not exist.
if not os.path.exists('db/capscheduler.db'):
    print('Creating database.')
    db.create_all()
    
@app.route('/', methods=['GET', 'POST'])
def index():
    # If the user arrives at the index page without a date, pick today.
    if 'meetingDate' in request.values: # Date exists in POST or GET
        meetingDate = request.values.get('meetingDate')
        return redirect('/schedule?meetingDate={}'.format(meetingDate))
    else: # Pick the next day that coincides with the meeting day.
        nextMeetingDay = date.today()
        while nextMeetingDay.weekday() != DAYNUM[meetingDay]:
            nextMeetingDay += timedelta(1)
        meetingDate = nextMeetingDay.strftime(DATEFMT)
        return redirect('/schedule?meetingDate={}'.format(meetingDate))

@app.route('/schedule', methods=['GET', 'POST'])
def schedule_window():
    if 'status' in request.values:
        pageStatus = request.values.get('status')
    else:
        pageStatus = ''
    if 'pageAction' in request.values:
        pageAction = request.values.get('pageAction')
    else:
        pageAction = ''

    # Grab variables for 'edit' pageAction
    eventData = []
    if pageAction == 'EditEvent':
        id = request.values.get('eventId')
        eventobj = Event.query.filter_by(eventId=int(id))
        eventData += [ eventobj[0].eventId ]
        eventData += [ eventobj[0].eventDate ]
        eventData += [ eventobj[0].startTime ]
        eventData += [ eventobj[0].stopTime ]
        eventData += [ eventobj[0].eventName ]
        eventData += [ eventobj[0].eventLdr ]
        eventData += [ eventobj[0].contactAccount ]
        eventData += [ eventobj[0].isAgreedTo ]
        eventData += [ eventobj[0].isEmailScheduled ]
        eventData += [ eventobj[0].isEmailSent ]
        eventData += [ eventobj[0].isEmailConfirmed ]

    if 'meetingDate' in request.values:
        meetingDate = request.values.get('meetingDate')
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
        queryResults = Event.query.filter_by(eventDate=meetingDate)
        sortedQueryResults = []
        minutes = {}
        # Populate minutes
        for account in CONTACT_ACCOUNTS:
            minutes[CONTACT_ABRVS[account]] = 0
        counter = result_length(queryResults)

        for i in range(0, counter):
            if queryResults[i].isDeleted != 1:
                minutes[CONTACT_ABRVS[queryResults[i].contactAccount]] += queryResults[i].contactMinutes
                row = '{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}'.format(queryResults[i].eventId, queryResults[i].eventDate, queryResults[i].startTime, \
                                                             queryResults[i].stopTime, queryResults[i].eventName, queryResults[i].eventLdr, \
                                                             CONTACT_ABRVS[queryResults[i].contactAccount], queryResults[i].isAgreedTo, \
                                                             queryResults[i].isEmailScheduled, queryResults[i].isEmailSent, queryResults[i].isEmailConfirmed)
                sortedQueryResults += [ row.split('|') ]
        # Convern minute and abrvs dictionaries to lists before sending them:
        minute_list = list(minutes.values())
        abrvs_list = list(CONTACT_ABRVS.values())
        return render_template('index.html', meetingDate=meetingDate, prevDate=prevDate, nextDate=nextDate, results=sortedQueryResults, status=pageStatus,
                                pageAction=pageAction, eventData=eventData, accounts=CONTACT_ACCOUNTS, minutes=minute_list, abrvs=abrvs_list)
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
            data += [ request.values.get(each) ]
            
        # Calculate contact minutes for new events.
        data += [ convert_times_to_minutes(data[2], data[1]) ]

        for each in [ 'isAgreedTo', 'isEmailScheduled', 'isEmailSent', 'isEmailConfirmed' ]:
            data += [ isin(each) ]

        # Create a new DB entry.
        newevent = Event(eventDate=data[0], startTime=data[1], stopTime=data[2], eventName=data[3], eventLdr=data[4], \
                         contactAccount=data[5], contactMinutes=data[6], isAgreedTo=data[7], isEmailScheduled=data[8], \
                         isEmailSent=data[9], isEmailConfirmed=data[10], isDeleted=0)
        # Commit the DB entry and send them back to the index page with the previous date.
        db.session.add(newevent)
        db.session.commit()
        newevent = ''
        # Add to statistics DB
        date = data[0].split('-')
        count_stats(date[0], date[1], data[5], data[6])
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
    meetingDate = request.values.get('meetingDate')
    id = request.values.get('eventId')
    status = "Event Updated"
    event = Event.query.filter_by(eventId=int(id)).first()
    event.eventDate = request.values.get('eventDate')
    event.startTime = request.values.get('startTime')
    event.stopTime = request.values.get('stopTime')
    event.eventName = request.values.get('eventName')
    event.eventLdr = request.values.get('eventLdr')
    event.contactAccount = request.values.get('contactAccount')

    # Calculate new contact hours.

    event.contactMinutes = convert_times_to_minutes(request.values.get('stopTime'), request.values.get('startTime'))

    event.isAgreedTo = isin('isAgreedTo')
    event.isEmailScheduled = isin('isEmailScheduled')
    event.isEmailSent = isin('isEmailSent')
    event.isEmailConfirmed = isin('isEmailConfirmed')
    event.isEmailDeleted = isin('isDeleted')
    db.session.commit()
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
    return redirect('/schedule?meetingDate={}'.format(meetingDate))
    

if __name__ == '__main__':
    #app.run(debug=True, host='0.0.0.0')
    manager.run()

