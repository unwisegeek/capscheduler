import os
from flask import Flask, render_template, request, redirect
from datetime import datetime, date, timedelta
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///capscheduler.db'
db = SQLAlchemy(app)

DAYNUM = { 'Monday': 0,
               'Tuesday': 1,
               'Wednesday': 2,
               'Thursday': 3,
               'Friday': 4,
               'Saturday': 5,
               'Sunday': 6,
}

DATEFMT = '%m-%d-%Y'
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
    isEventDeleted = db.Column(db.Integer, unique=False, nullable=False)

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
        meetingDate = datetime.strptime(meetingDate, DATEFMT)
        prevDate = meetingDate + timedelta(-7)
        prevDate = prevDate.strftime(DATEFMT)
        nextDate = meetingDate + timedelta(+7)
        nextDate = nextDate.strftime(DATEFMT)
        meetingDate = meetingDate.strftime('%Y-%m-%d')
        return render_template('index.html', meetingDate=meetingDate, prevDate=prevDate, nextDate=nextDate)
    else:
        # Redirect if the date has not been set.
        redirect('/')

@app.route('/newevent', methods=['GET', 'POST'])
def newevent():
    # Check that all variables that are needed to create an event in the database are there.
    allVarsExist = True
    for each in [ "eventDate", "startTime", "stopTime", "eventName", "eventLdr", "isConfirmed", "isEmailScheduled", "isEmailSent", "isEmailConfirmed" ]:
        if each not in request.values:
            allVarsExist = False
    if allVarsExist:
        # Create list of variable values.
        data[0] = request.values.get('eventDate')
        data[1] = request.values.get('startTime')
        data[2] = request.values.get('stopTime')
        data[3] = request.values.get('eventName')
        data[4] = request.values.get('eventLdr')
        data[5] = request.values.get('isAgreedTo')
        data[6] = request.values.get('isEmailScheduled')
        data[7] = request.values.get('isEmailSent')
        data[8] = request.values.get('isEmailConfirmed')
        data[9] = request.values.get('isDeleted')
        # Create a new DB entry.
        newevent = Event(eventDate=data[0], startTime=data[1], stopTime=data[2], eventName=data[3], eventLdr=data[5], \
                         isAgreedTo=data[6], isEmailScheduled=data[7], isEmailSent=data[8], isEmailConfirmed=data[8], \
                         isDeleted=data[9])
        # Commit the DB entry and send them back to the index page with the previous date.
        db.session.add(newevent)
        db.session.commit()
        newevent = ""
        # Redirect
        meetingDate = request.values.get('meetingDate')
        redirect('/schedule?meetingDate={}'.format(meetingDate))



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')