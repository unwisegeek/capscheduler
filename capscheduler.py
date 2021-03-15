from flask import Flask, render_template, request, redirect
from datetime import datetime, date, timedelta
# from flask_sqlalchemy import flask_sqlalchemy

app = Flask(__name__)

def get_initial_date():
    """
    Returns a string with the following format: YYYY-MM-DD
    """
    DAYNUM = { 'Monday': 0,
               'Tuesday': 1,
               'Wednesday': 2,
               'Thursday': 3,
               'Friday': 4,
               'Saturday': 5,
               'Sunday': 6,
    }
    next_meeting = date.today()
    while next_meeting.weekday() != DAYNUM['Thursday']:
        next_meeting += timedelta(1)
    return next_meeting.strftime("%Y-%m-%d")

def get_other_dates(meetingDate):
    """
    Returns two strings with the following format: YYYY-MM-DD
    
    First value is the date entered -7, and the second value is the date entered + 7.    
    """
    target = datetime.strptime(meetingDate, '%Y-%m-%d')
    offset = timedelta(7)
    prevDate = target - offset
    nextDate = target + offset
    return prevDate.strftime('%Y-%m-%d'), nextDate.strftime('%Y-%m-%d')
    
@app.route('/')
def index():
    meetingDate = get_initial_date()
    return redirect('/schedule?meetingDate={}'.format(meetingDate))

@app.route('/schedule', methods=['GET', 'POST'])
def schedule_window():
    if "meetingDate" in request.values:
        meetingDate = request.values.get('meetingDate')
        prevDate, nextDate = get_other_dates(meetingDate)
        return render_template('index.html', meetingDate=meetingDate, prevDate=prevDate, nextDate=nextDate)
    else:
        return '', 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')