import os
from flask import Flask, render_template, request, redirect
from datetime import datetime, date, timedelta
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///capscheduler.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

DAYNUM = { 'Monday': 0,
               'Tuesday': 1,
               'Wednesday': 2,
               'Thursday': 3,
               'Friday': 4,
               'Saturday': 5,
               'Sunday': 6,
}

DATEFMT = '%Y-%m-%d'
meetingDay = 'Thursday'

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
    isAgreedTo = db.Column(db.Integer, unique=False, nullable=False)
    isEmailScheduled = db.Column(db.Integer, unique=False, nullable=False)
    isEmailSent = db.Column(db.Integer, unique=False, nullable=False)
    isEmailConfirmed = db.Column(db.Integer, unique=False, nullable=False)
    isDeleted = db.Column(db.Integer, unique=False, nullable=False)

# Initialize the database file if one does not exist.
if not os.path.exists('capscheduler.db'):
    print("Creating database.")
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
    if "meetingDate" in request.values:
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
        counter = 0
        while True:
            try:
                a = queryResults[counter].eventId
                counter += 1
            except:
                break
        for i in range(0, counter):
            if queryResults[i].isDeleted != 1:
                row = "{}|{}|{}|{}|{}|{}|{}|{}|{}|{}".format(queryResults[i].eventId, queryResults[i].eventDate, queryResults[i].startTime, \
                                                             queryResults[i].stopTime, queryResults[i].eventName, queryResults[i].eventLdr, \
                                                             queryResults[i].isAgreedTo, queryResults[i].isEmailScheduled, queryResults[i].isEmailSent, \
                                                             queryResults[i].isEmailConfirmed)
                sortedQueryResults += [ row.split('|') ]
        return render_template('index.html', meetingDate=meetingDate, prevDate=prevDate, nextDate=nextDate, results=sortedQueryResults)
    else:
        # Redirect if the date has not been set.
        return redirect('/')

@app.route('/newevent', methods=['GET', 'POST'])
def newevent():
    # Check that all variables that are needed to create an event in the database are there.
    allVarsExist = True
    for each in [ "eventDate", "startTime", "stopTime", "eventName", "eventLdr", "isAgreedTo", "isEmailScheduled", "isEmailSent", "isEmailConfirmed" ]:
        if each not in request.values:
            allVarsExist = False
    if allVarsExist:
        # Create list of variable values.
        data = []
        data += [ request.values.get('eventDate') ]
        data += [ request.values.get('startTime') ]
        data += [ request.values.get('stopTime') ]
        data += [ request.values.get('eventName') ]
        data += [ request.values.get('eventLdr') ]
        data += [ request.values.get('isAgreedTo') ]
        data += [ request.values.get('isEmailScheduled') ]
        data += [ request.values.get('isEmailSent') ]
        data += [ request.values.get('isEmailConfirmed') ]
        data += [ request.values.get('isDeleted') ]
        # Create a new DB entry.
        newevent = Event(eventDate=data[0], startTime=data[1], stopTime=data[2], eventName=data[3], eventLdr=data[4], \
                         isAgreedTo=data[5], isEmailScheduled=data[6], isEmailSent=data[7], isEmailConfirmed=data[8], \
                         isDeleted=9)
        # Commit the DB entry and send them back to the index page with the previous date.
        db.session.add(newevent)
        db.session.commit()
        newevent = ""
        # Redirect
        meetingDate = request.values.get('meetingDate')
        return redirect('/schedule?meetingDate={}'.format(meetingDate))
    return ""


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')