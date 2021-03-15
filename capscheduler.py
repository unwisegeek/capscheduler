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
    eventId = db.Column(db.Integer, primary_key=True)
    eventDate = db.Column(db.String(10), unique=False, nullable=False)
    startTime = db.Column(db.String(5), unique=False, nullable=False)
    stopTime = db.Column(db.String(5), unique=False, nullable=False)
    eventName = db.Column(db.string(80), unique=False, nullable=False)
    eventLdr = db.Column(db.string(80), unique=False, nullable=False)
    isConfirmed = db.Column(db.Integer, unique=False, nullable=False)
    isEmailScheduled = db.Column(db.Integer, unique=False, nullable=False)
    isEmailSent = db.Column(db.Integer, unique=False, nullable=False)
    isEmailConfirmed = db.Column(db.Integer, unique=False, nullable=False)

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')