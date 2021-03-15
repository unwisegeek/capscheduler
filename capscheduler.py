from flask import Flask, render_template, request, redirect
from datetime import datetime, date, timedelta
# from flask_sqlalchemy import flask_sqlalchemy

app = Flask(__name__)

DAYNUM = { 'Monday': 0,
               'Tuesday': 1,
               'Wednesday': 2,
               'Thursday': 3,
               'Friday': 4,
               'Saturday': 5,
               'Sunday': 6,
}
    
@app.route('/')
def index():
    nextMeetingDay = date.today()
    while nextMeetingDay.weekday() != DAYNUM['Thursday']:
        nextMeetingDay += timedelta(1)
    meetingDate = nextMeetingDay.stftime("%Y-%m-%d")
    return redirect('/schedule?meetingDate={}'.format(meetingDate))

@app.route('/schedule', methods=['GET', 'POST'])
def schedule_window():
    if "meetingDate" in request.values:
        meetingDate = request.values.get('meetingDate')
        prevDate = meetingDate.strptime("%Y-%m-%d") + timedelta(-7)
        prevDate = prevDate.strftime("%Y-%m-%d")
        nextDate = meetingDate.strptime("%Y-%m-%d") + timedelta(+7)
        nextDate = nextDate.strftime("%Y-%m-%d")
        return render_template('index.html', meetingDate=meetingDate, prevDate=prevDate, nextDate=nextDate)
    else:
        return '', 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')