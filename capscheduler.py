import hashlib
import json
import os
from datetime import date, datetime, timedelta

import requests
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_dance.consumer import oauth_authorized, oauth_error
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin, SQLAlchemyStorage
from flask_dance.contrib.google import make_google_blueprint
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager, Server
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from oauthlib.oauth2 import WebApplicationClient
from sqlalchemy.orm.exc import NoResultFound

from config import (
    ADMIN_EMAIL,
    DB_STRING,
    GOOGLE_AUTH_URI,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_DISCOVERY_URL,
    GOOGLE_REDIRECT_URI,
    GOOGLE_TOKEN_URI,
    INSTALL_DIR,
    meetingDay,
)
from const import (
    BRANCH,
    CONTACT_ABRVS,
    CONTACT_ACCOUNTS,
    CONTACT_ACCT_REQS,
    DATEFMT,
    DAYNUM,
    LAST_UPDATED,
    MONTHNUM,
)

os.chdir(INSTALL_DIR)

app = Flask(__name__)
if DB_STRING == "":
    raise Exception("Please configure the DB_STRING in config.py.")
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = DB_STRING
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Check for secret_key file.
if not os.path.exists(".secret_key"):
    raise Exception(
        "Please generate a secret key.\r\nEx: dd if=/dev/random bs=100M count=1 | sha256sum | cut -d "
        " -f1 > .secret_key"
    )
else:
    app.config["SECRET_KEY"] = open("./.secret_key", "r").read().encode("utf8")

# Flask User session management
login_manager = LoginManager()
login_manager.login_view = "google.login"

# Oauth 2 Client Setup
client = WebApplicationClient(GOOGLE_CLIENT_ID)

# Configure Server-side sessions
app.config["SESSION_TYPE"] = "null"
# app.config['SESSION_USE_SIGNER'] = True
sess = Session()


# Configure database migratiosn
migrate = Migrate(app, db, render_as_batch=True)
manager = Manager(app)

manager.add_command("db", MigrateCommand)
manager.add_command(
    "runserver", Server(host="0.0.0.0", port=5000, use_debugger=True, use_reloader=True)
)


def result_length(set):
    counter = 0
    while True:
        try:
            type(set[counter].eventId)
            counter += 1
        except IndexError:
            break
    return counter


def convert_bool_to_ballot(targValue):
    if targValue == 1:
        return "&#9744"
    else:
        return "&#9745"


def convert_times_to_minutes(stopTime, startTime, format="%H:%M"):
    difference = datetime.strptime(stopTime, format) - datetime.strptime(
        startTime, format
    )
    minutes = difference.total_seconds() // 60
    return int(minutes)


def count_stats(year, month, acct, mins):
    """
    Adds contact hours to stats db

    Requires: year(int), month(int), acct(str), mins(int)
    """
    try:
        statsobj = (
            MonthlyStats.query.filter_by(statsYear=int(year))
            .filter_by(statsMonth=int(month))
            .filter_by(contactAccount=acct)
        )
        statsobj[0].contactMinutes = statsobj[0].contactMinutes + mins
    except IndexError:
        newstat = MonthlyStats(
            statsYear=int(year),
            statsMonth=int(month),
            contactAccount=acct,
            contactMinutes=int(mins),
        )
        db.session.add(newstat)
    db.session.commit()
    return


def uncount_stats(year, month, acct, mins):
    """
    Removes contact hours from stats db

    Requires: year, month, acct, mins
    """
    try:
        statsobj = (
            MonthlyStats.query.filter_by(statsYear=int(year))
            .filter_by(statsMonth=int(month))
            .filter_by(contactAccount=acct)
        )
        statsobj[0].contactMinutes = statsobj[0].contactMinutes - mins
        db.session.commit()
    except IndexError:
        pass
    return


def get_first_meeting_day(month, year):
    targetDay = datetime.strptime("{}-{}-01".format(year, month), "%Y-%m-%d")
    while targetDay.weekday() != DAYNUM[meetingDay]:
        targetDay += timedelta(days=1)
    return targetDay


def get_meeting_dates_in_month(month, year):
    listOfDates = []
    firstDay = get_first_meeting_day(month, year)
    # Find the first meeting day
    while firstDay.weekday() != DAYNUM[meetingDay]:
        firstDay += timedelta(days=1)

    while firstDay.month == month:
        listOfDates += [firstDay.strftime(DATEFMT)]
        firstDay += timedelta(days=7)

    return listOfDates


# Create the event model for the database.
class Event(db.Model):
    __tablename__ = "events"
    __table_args__ = {"sqlite_autoincrement": True}
    eventId = db.Column(db.Integer, primary_key=True)
    eventDate = db.Column(db.String(10), unique=False, nullable=False)
    startTime = db.Column(db.String(5), unique=False, nullable=False)
    stopTime = db.Column(db.String(5), unique=False, nullable=False)
    eventName = db.Column(db.String(80), unique=False, nullable=False)
    eventLdr = db.Column(db.String(80), unique=False, nullable=False)
    contactAccount = db.Column(db.String(40), unique=False, nullable=False)
    contactMinutes = db.Column(db.Integer, unique=False, nullable=False)
    isAgreedTo = db.Column(db.Integer, unique=False, nullable=False, server_default="0")
    isEmailScheduled = db.Column(
        db.Integer, unique=False, nullable=False, server_default="0"
    )
    isEmailSent = db.Column(
        db.Integer, unique=False, nullable=False, server_default="0"
    )
    isEmailConfirmed = db.Column(
        db.Integer, unique=False, nullable=False, server_default="0"
    )
    isEmailThanked = db.Column(
        db.Integer, unique=False, nullable=False, server_default="0"
    )
    isOnSiteViz = db.Column(
        db.Integer, unique=False, nullable=False, server_default="0"
    )
    isDeleted = db.Column(db.Integer, unique=False, nullable=False, server_default="0")
    isStated = db.Column(db.Integer, unique=False, nullable=False, server_default="0")


class MonthlyStats(db.Model):
    __tablename__ = "monthly-statistics"
    __table_args__ = {"sqlite_autoincrement": True}
    statsId = db.Column(db.Integer, primary_key=True)
    statsYear = db.Column(db.Integer, unique=False, nullable=False)
    statsMonth = db.Column(db.Integer, unique=False, nullable=False)
    contactAccount = db.Column(db.String(30), unique=False, nullable=False)
    contactMinutes = db.Column(db.Integer, unique=False, nullable=False)


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = {"sqlite_autoincrement": True}
    userId = db.Column(db.Integer, primary_key=True)
    userFirstName = db.Column(db.String(30), unique=False, nullable=False)
    userLastName = db.Column(db.String(30), unique=False, nullable=False)
    userRank = db.Column(db.String(30), unique=False, nullable=False)
    userEmail = db.Column(db.String(50), unique=True, nullable=False)
    userLoginLock = db.Column(
        db.Integer, unique=False, nullable=False, server_default="0"
    )
    userPermissions = db.Column(
        db.String(128), unique=False, nullable=False, server_default="viewer"
    )
    userProfilePic = db.Column(db.String(128), unique=False, nullable=True)

    def is_active(self):
        if self.userLoginLock == "0":
            return True
        else:
            return False

    def get_id(self):
        return self.userId

    def get_permissions(self):
        return self.userPermissions.split(",")

    def has_permission(self, perm):
        if perm in self.userPermissions:
            return True


class OAuth(OAuthConsumerMixin, db.Model):
    provider_user_id = db.Column(db.String(256), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey(User.userId), nullable=False)
    user = db.relationship(User)


GOOGLE_BLUEPRINT = make_google_blueprint(
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    redirect_url=GOOGLE_REDIRECT_URI,
    scope=["openid", "profile", "email"],
    storage=SQLAlchemyStorage(OAuth, db.session, user=current_user),
    redirect_to="schedule",
    hosted_domain="mariettacap.org",
)

app.register_blueprint(GOOGLE_BLUEPRINT)
login_manager.init_app(app)


@login_manager.user_loader
# def load_user(email):
#     user = User.query.filter_by(userEmail=str(email)).first()
#     return user
def load_user(user_id):
    return User.query.get(int(user_id))


@oauth_authorized.connect_via(GOOGLE_BLUEPRINT)
def google_logged_in(blueprint, token):
    if not token:
        flash("Failed to log in.", category="error")
        return False

    resp = blueprint.session.get("/oauth2/v1/userinfo")
    if not resp.ok:
        msg = "Failed to fetch user info."
        flash(msg, category="error")
        return False

    info = resp.json()
    user_id = info["id"]

    # Find this OAuth Token in the database or create it
    query = OAuth.query.filter_by(provider=blueprint.name, provider_user_id=user_id)
    try:
        oauth = query.one()
    except NoResultFound:
        oauth = OAuth(provider=blueprint.name, provider_user_id=user_id, token=token)

    if oauth.user:
        login_user(oauth.user)
        flash("Successfully signed in.")
    else:
        user = User(userEmail=["email"])
        oauth.user = user
        db.session.add_all([user, oauth])
        db.session.commit()
        login_user(user)
        flash("Successfully signed in.")
    return False


@oauth_error.connect_via(GOOGLE_BLUEPRINT)
def google_error(blueprint, message, response):
    msg = f"OAuth error from {app.name}! message={message} response={response}"
    flash(msg, category="error")


# Initialize the database file if one does not exist.
if not os.path.exists("./capscheduler.db"):
    print("Creating database.")
    db.create_all()


@app.route("/", methods=["GET", "POST"])
def index():
    # Get GET variables and come back with them in a session.
    keylist = []
    for each in request.values.keys():
        keylist += [each]

    if len(keylist) > 0:
        for each in request.values.keys():
            session[each] = request.values.get(each)
        return redirect("/")

    pageStatus = session.get("status", "")
    if not session.get("userId", False):
        session.clear()
        return render_template("login.html", status=pageStatus)
    # If the user arrives at the index page with a date, use it.
    if (
        "meetingDate" in request.values or session.get("meetingDate", "-1") != "-1"
    ):  # Date exists in POST or GET
        meetingDate = session.get("meetingDate", "-1")
        if meetingDate == "-1":
            meetingDate = request.values.get("meetingDate")
            session["meetingDate"] = meetingDate
            return redirect("/schedule")
        return redirect("/schedule")
    else:  # Pick the next day that coincides with the meeting day.
        nextMeetingDay = date.today()
        while nextMeetingDay.weekday() != DAYNUM[meetingDay]:
            nextMeetingDay += timedelta(1)
        meetingDate = nextMeetingDay.strftime(DATEFMT)
        session["meetingDate"] = meetingDate
        return redirect("/schedule")


@app.route("/schedule", methods=["GET", "POST"])
def schedule_window():
    # If we get GET or POST variables, convert them to session data:
    # session.clear()

    keylist = []
    for each in request.values.keys():
        keylist += [each]

    if len(keylist) > 0:
        for each in request.values.keys():
            session[each] = request.values.get(each)
        return redirect(
            "/schedule"
        )  # Come back with all GET variables converted to session

    pageStatus = session.get("status", "")
    if pageStatus != "":
        session.pop("status")
    pageAction = session.get("pageAction", "")
    id = session.get("eventId", -99)

    # Grab variabes for user data
    userId = session.get("userId", False)
    userData = []
    if not userId:
        return redirect("/")
    else:
        userobj = User.query.filter_by(userId=userId)
        userData += [userobj[0].userRank]
        userData += [userobj[0].userFirstName]
        userData += [userobj[0].userLastName]
        userData += [userobj[0].userPermissions]

    # Grab variables for 'edit' pageAction
    eventData = []
    if pageAction == "EditEvent":
        eventobj = Event.query.filter_by(eventId=int(id))
        eventData += [eventobj[0].eventId]
        eventData += [eventobj[0].eventDate]
        eventData += [eventobj[0].startTime]
        eventData += [eventobj[0].stopTime]
        eventData += [eventobj[0].eventName]
        eventData += [eventobj[0].eventLdr]
        eventData += [CONTACT_ABRVS[eventobj[0].contactAccount]]
        eventData += [eventobj[0].isAgreedTo]
        eventData += [eventobj[0].isEmailScheduled]
        eventData += [eventobj[0].isEmailSent]
        eventData += [eventobj[0].isEmailConfirmed]
        eventData += [eventobj[0].isEmailThanked]
        eventData += [eventobj[0].isOnSiteViz]
        eventData += [eventobj[0].isStated]

    if session.get("meetingDate", "-1") != "-1":
        meetingDate = session.get("meetingDate", "-1")

        # Account for meetingDate coming back in a different format
        if meetingDate[2] == "-":  # Month First
            meetingDate = datetime.strptime(meetingDate, DATEFMT)
        else:  # Year First
            meetingDate = datetime.strptime(meetingDate, "%Y-%m-%d")

        prevDate = meetingDate + timedelta(-7)
        prevDate = prevDate.strftime(DATEFMT)
        nextDate = meetingDate + timedelta(+7)
        nextDate = nextDate.strftime(DATEFMT)
        meetingDate = meetingDate.strftime("%Y-%m-%d")

        # Get results from DB
        queryResults = Event.query.filter_by(eventDate=meetingDate).order_by(
            Event.startTime
        )
        date = meetingDate.split("-")
        sortedQueryResults = []
        minutes = {}
        monthly_minutes = []

        # Populate minutes and monthly_minutes
        for account in CONTACT_ACCOUNTS:
            minutes[CONTACT_ABRVS[account]] = 0
            queryStats = (
                MonthlyStats.query.filter_by(statsYear=int(date[0]))
                .filter_by(statsMonth=int(date[1]))
                .filter_by(contactAccount=account)
            )
            try:
                monthly_minutes += [queryStats[0].contactMinutes]
            except IndexError:
                monthly_minutes += [0]

        counter = result_length(queryResults)
        for i in range(0, counter):
            if queryResults[i].isDeleted != 1:
                minutes[CONTACT_ABRVS[queryResults[i].contactAccount]] += queryResults[
                    i
                ].contactMinutes
                row = "{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}".format(
                    queryResults[i].eventId,
                    queryResults[i].eventDate,
                    queryResults[i].startTime,
                    queryResults[i].stopTime,
                    queryResults[i].eventName,
                    queryResults[i].eventLdr,
                    CONTACT_ABRVS[queryResults[i].contactAccount],
                    queryResults[i].isAgreedTo,
                    queryResults[i].isEmailScheduled,
                    queryResults[i].isEmailSent,
                    queryResults[i].isEmailConfirmed,
                    queryResults[i].isOnSiteViz,
                    queryResults[i].isEmailThanked,
                )
                sortedQueryResults += [row.split("|")]

        # Convert minute and abrvs dictionaries to lists before sending them:
        minute_list = list(minutes.values())
        abrvs_list = list(CONTACT_ABRVS.values())
        return render_template(
            "index.html",
            meetingDate=meetingDate,
            prevDate=prevDate,
            nextDate=nextDate,
            results=sortedQueryResults,
            status=pageStatus,
            pageAction=pageAction,
            eventData=eventData,
            accounts=CONTACT_ACCOUNTS,
            minutes=minute_list,
            mminutes=monthly_minutes,
            abrvs=abrvs_list,
            eventId=id,
            session=session,
            userData=userData,
            branch=BRANCH,
            last_updated=LAST_UPDATED,
        )
    else:
        # Redirect if the date has not been set.
        return redirect("/")


@app.route("/profile", methods=["GET", "POST"])
def profile():
    # Get GET variables and come back with them in a session.
    keylist = []
    for each in request.values.keys():
        keylist += [each]

    if len(keylist) > 0:
        for each in request.values.keys():
            session[each] = request.values.get(each)
        return redirect("/profile")

    opMode = session.get("mode", "view")
    pageStatus = session.get("status", "")
    userId = session.get("userId", False)
    # userInfo = session.get("userInfo", False)

    if not userId:
        session.clear()
        return render_template("login.html", status=pageStatus)

    if opMode in ("view", "edit", "viewall"):
        userobj = User.query.filter_by(userId=userId).first()
        userData = []
        userData += [userobj.userId]
        userData += [userobj.userRank]
        userData += [userobj.userFirstName]
        userData += [userobj.userLastName]
        userData += [userobj.userEmail]
        userData += [userobj.userPermissions]

        return render_template(
            "profile.html",
            mode=opMode,
            status=pageStatus,
            userData=userData,
        )


@app.route("/saveprofile", methods=["GET", "POST"])
def saveprofile():
    keylist = []
    for each in request.values.keys():
        keylist += [each]

    if len(keylist) > 0:
        for each in request.values.keys():
            session[each] = request.values.get(each)
        return redirect("/saveprofile")
    # early_session = session
    trackvar = ""
    userobj = User.query.filter_by(userId=session["userId"]).first()

    userobj.userFirstName = session["userFirstName"]
    session.pop("userFirstName")
    userobj.userLastName = session["userLastName"]
    session.pop("userLastName")
    userobj.userRank = session["userRank"]
    session.pop("userRank")

    perms = []
    if session.get("viewer", False):
        trackvar += session.get("viewer")
        perms += ["viewer"]
        session.pop("viewer")
    if session.get("scheduling", False):
        trackvar += session.get("scheduling")
        perms += ["scheduling"]
        session.pop("scheduling")
    if session.get("commander", False):
        trackvar += session.get("commander")
        perms += ["commander"]
        session.pop("commander")
    if session.get("editor", False):
        trackvar += session.get("editor")
        perms += ["editor"]
        session.pop("editor")
    if session.get("admin", False):
        trackvar += session.get("admin")
        perms += ["admin"]
        session.pop("admin")
    perms_str = ""
    for i in range(0, len(perms)):
        perms_str += perms[i]
        if i < len(perms) - 1:
            perms_str += ","

    userobj.userPermissions = perms_str
    db.session.commit()
    session["mode"] = "view"
    return redirect("/profile")


@app.route("/newevent", methods=["GET", "POST"])
def newevent():
    def isin(flag):
        if flag in request.values:
            return 1
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
    meetingDate = request.values.get("meetingDate")
    for each in [
        "eventDate",
        "startTime",
        "stopTime",
        "eventName",
        "eventLdr",
        "contactAccount",
    ]:
        if each not in request.values:
            reqVarsExist = False
    if reqVarsExist:
        # Create list of variable values.
        data = {}
        for each in [
            "eventDate",
            "startTime",
            "stopTime",
            "eventName",
            "eventLdr",
            "contactAccount",
        ]:
            if each == "contactAccount":
                data[each] = abrv_to_acct(request.values.get(each))
            else:
                data[each] = request.values.get(each)

        # Ensure startTime and endTime are converted from HHMM to HH:MM format
        if len(data["startTime"]) == 4 and ":" not in data["startTime"]:
            # Time in HHMM format. Rebuild into HH:MM format
            data["startTime"] = "{}{}:{}{}".format(
                data["startTime"][0],
                data["startTime"][1],
                data["startTime"][2],
                data["startTime"][3],
            )
        if len(data["stopTime"]) == 4 and ":" not in data["stopTime"]:
            # Time in HHMM format. Rebuild into HH:MM format
            data["stopTime"] = "{}{}:{}{}".format(
                data["stopTime"][0],
                data["stopTime"][1],
                data["stopTime"][2],
                data["stopTime"][3],
            )

        # Calculate contact minutes for new events.
        data["contactMinutes"] = convert_times_to_minutes(
            data["stopTime"], data["startTime"]
        )

        for each in [
            "isAgreedTo",
            "isEmailScheduled",
            "isEmailSent",
            "isEmailConfirmed",
            "isEmailThanked",
            "isOnSiteViz",
        ]:
            data[each] = isin(each)

        # Create a new DB entry.
        newevent = Event(
            eventDate=data["eventDate"],
            startTime=data["startTime"],
            stopTime=data["stopTime"],
            eventName=data["eventName"],
            eventLdr=data["eventLdr"],
            contactAccount=data["contactAccount"],
            contactMinutes=data["contactMinutes"],
            isAgreedTo=data["isAgreedTo"],
            isEmailScheduled=data["isEmailScheduled"],
            isEmailSent=data["isEmailSent"],
            isEmailConfirmed=data["isEmailConfirmed"],
            isEmailThanked=data["isEmailThanked"],
            isOnSiteViz=data["isOnSiteViz"],
            isDeleted=0,
        )
        # Commit the DB entry and send them back to the index page with the previous date.
        db.session.add(newevent)
        db.session.commit()
        newevent = ""
        # Add to statistics DB
        date = data["eventDate"].split("-")
        count_stats(date[0], date[1], data["contactAccount"], data["contactMinutes"])
        # Clear session variables that no longer need to be there
        try:
            session.pop("pageAction")
        except ValueError:
            pass
        except KeyError:
            pass
        try:
            session.pop("eventId")
        except ValueError:
            pass
        except KeyError:
            pass
        # Redirect
        return redirect(
            "/schedule?meetingDate={}&status=Event%20Added".format(meetingDate)
        )
    return redirect(
        "/schedule?meetingDate={}&status=Error%20Adding%20Event".format(meetingDate)
    )


@app.route("/delete", methods=["GET", "POST"])
def deleteevent():
    meetingDate = request.values.get("meetingDate")
    id = request.values.get("eventId")
    eventobj = Event.query.filter_by(eventId=int(id)).first()
    eventobj.isDeleted = 1
    date = eventobj.eventDate.split("-")
    uncount_stats(date[0], date[1], eventobj.contactAccount, eventobj.contactMinutes)
    db.session.commit()
    status = "Event Deleted"
    return redirect("/schedule?meetingDate={}&status={}".format(meetingDate, status))


@app.route("/edit", methods=["POST"])
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

    meetingDate = request.values.get("meetingDate")
    id = request.values.get("eventId")
    status = "Event Updated"
    event = Event.query.filter_by(eventId=int(id)).first()
    event.eventDate = request.values.get("eventDate")
    event.startTime = request.values.get("startTime")
    event.stopTime = request.values.get("stopTime")
    event.eventName = request.values.get("eventName")
    event.eventLdr = request.values.get("eventLdr")
    event.contactAccount = abrv_to_acct(request.values.get("contactAccount"))

    # Calculate new contact hours.

    event.contactMinutes = convert_times_to_minutes(
        request.values.get("stopTime"), request.values.get("startTime")
    )

    event.isAgreedTo = isin("isAgreedTo")
    event.isEmailScheduled = isin("isEmailScheduled")
    event.isEmailSent = isin("isEmailSent")
    event.isEmailConfirmed = isin("isEmailConfirmed")
    event.isEmailThanked = isin("isEmailThanked")
    event.isOnSiteViz = isin("isOnSiteViz")
    event.isEmailDeleted = isin("isDeleted")
    db.session.commit()
    try:
        session.pop("pageAction")
    except ValueError:
        pass
    try:
        session.pop("eventId")
    except ValueError:
        pass
    return redirect("/schedule?meetingDate={}&status={}".format(meetingDate, status))


@app.route("/email", methods=["GET", "POST"])
def email():
    # Get GET variables and come back with them in a session.
    keylist = []
    for each in request.values.keys():
        keylist += [each]

    if len(keylist) > 0:
        for each in request.values.keys():
            session[each] = request.values.get(each)
        return redirect("/email")

    if session.get("meetingDate", "-1") != "-1":
        meetingDate = session.get("meetingDate", "-1")
    else:
        return redirect("/")

    pageStatus = session.get("status", "")
    if pageStatus != "":
        session.pop("status")

    tmpdate = datetime.strptime(meetingDate, DATEFMT)
    prevDate = tmpdate + timedelta(-7)
    prevDate = prevDate.strftime(DATEFMT)
    nextDate = tmpdate + timedelta(+7)
    nextDate = nextDate.strftime(DATEFMT)
    meetingDate = datetime.strftime(tmpdate, "%Y-%m-%d")

    # Get all events for meeting date
    queryResults = Event.query.filter_by(eventDate=meetingDate).order_by(
        Event.startTime
    )
    eventData = []
    counter = result_length(queryResults)
    for i in range(0, counter):
        if queryResults[i].isDeleted != 1:
            row = "{}|{}|{}|{}".format(
                queryResults[i].startTime,
                queryResults[i].stopTime,
                queryResults[i].eventName,
                queryResults[i].eventLdr,
            )
            eventData += [row.split("|")]
    return render_template(
        "email.html",
        meetingDate=meetingDate,
        nextDate=nextDate,
        prevDate=prevDate,
        status=pageStatus,
        data=eventData,
    )


@app.route("/recalculatestats", methods=["GET", "POST"])
def recalcstats():
    meetingDate = request.values.get("meetingDate")
    eventQuery = Event.query
    MonthlyStats.query.delete()

    for i in range(0, result_length(eventQuery)):
        if eventQuery[i].isDeleted != 1:
            date = eventQuery[i].eventDate.split("-")
            count_stats(
                date[0],
                date[1],
                eventQuery[i].contactAccount,
                eventQuery[i].contactMinutes,
            )  # year, month, acct, mins
            eventQuery[i].isStated = 1
            db.session.commit()
    return redirect(
        "/schedule?meetingDate={}&status=Stats Recalculated".format(meetingDate)
    )


# @app.route("/login", methods=["GET", "POST"])
# def login():
#     # google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
#     # auth_endpoint = google_provider_cfg["authorization_endpoint"]

#     # request_uri = client.prepare_request_uri(
#     #     auth_endpoint,
#     #     redirect_uri=GOOGLE_REDIRECT_URI,
#     # )
#     # return redirect(request_uri)
#     return redirect(url_for("login"))


@app.route("/callback", methods=["GET"])
def callback():
    LOGIN_ERROR_REDIRECT = "/?status=Error has occurred. Please try again."
    authorization_code = request.args.get("code")
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    token_endpoint = google_provider_cfg["token_endpoint"]
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authroization_response=request.url,
        redirect_url=request.base_url,
        code=authorization_code,
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )
    client.parse_request_body_response(json.dumps(token_response.json()))

    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    if userinfo_response.json().get("email_verified"):
        users_email = userinfo_response.json()["email"]
        userobj = User.query.filter_by(userEmail=users_email).first()
        if userobj:
            session["userId"] = userobj.userId
            login_user(userobj)
            return redirect("/")
        else:
            session["mode"] = "edit"
            # Create user sketch to be edited
            if userinfo_response.json().get("email") == ADMIN_EMAIL:
                perms = "viewer,admin"
            else:
                perms = "viewer"
            newuser = User(
                userRank="",
                userFirstName=userinfo_response.json()["given_name"],
                userLastName=userinfo_response.json()["family_name"],
                userEmail=userinfo_response.json()["email"],
                userPermissions=perms,
            )
            # Commit the DB entry and send them back to the index page with the previous date.
            db.session.add(newuser)
            db.session.commit()
            userobj = User.query.filter_by(userEmail=users_email).first()
            session["userId"] = userobj.userId
            return redirect("/profile")
    else:
        return redirect(LOGIN_ERROR_REDIRECT)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    logout_user()
    session.clear()
    return redirect("/")


@app.route("/navmenu-handler", methods=["GET", "POST"])
def navmenu():
    destination = request.values.get("destination", False)
    referrer = request.values.get("referrer", False)
    if destination and referrer:
        if "'/{}'".format(destination) in str(
            app.url_map
        ):  # Confirm the selected menu item is a valid route
            return redirect("/{}".format(destination))
        else:
            return redirect("/{}?status=Option not implemented.".format(referrer))
    else:
        return redirect("/")


@app.route("/frame", methods=["GET", "POST"])
def schedframe():
    # Get GET and POST variables and come back with them in a session.
    keylist = []
    for each in request.values.keys():
        keylist += [each]

    if len(keylist) > 0:
        for each in request.values.keys():
            session[each] = request.values.get(each)
        return redirect("/frame")

    frametarget = session.get("frametarget", "blank")
    if not frametarget or frametarget == "blank":
        return render_template("frame.html", frametarget=frametarget)
    elif frametarget == "todo":
        listItems = []
        listMonths = []
        tmp_content = []
        listNotices = []

        def get_target_dates():
            target_dates = []
            nextMeetingDate = datetime.today()
            # Add this month so it's this month and the next three in advance.
            target_dates = [
                {"year": nextMeetingDate.year, "month": nextMeetingDate.month}
            ]
            while nextMeetingDate.weekday() != DAYNUM[meetingDay]:
                nextMeetingDate += timedelta(days=1)

            # Extrapolate the next three month numbers from today's date
            target_dates = [
                {"year": nextMeetingDate.year, "month": nextMeetingDate.month}
            ]

            # Build the target_dates list out
            for i in range(1, 4):
                cur_month = target_dates[i - 1]["month"]
                cur_year = target_dates[i - 1]["year"]
                if cur_month + 1 > 12:
                    next_month = 1
                    next_year = cur_year + 1
                else:
                    next_month = cur_month + 1
                    next_year = cur_year
                target_dates += [{"year": next_year, "month": next_month}]
            return target_dates

        def contact_hour_check(targetDate):
            new_content = []

            # Get queries for those months from monthly-statistics
            month = targetDate["month"]
            year = targetDate["year"]
            for acct in CONTACT_ACCT_REQS.keys():
                statsobj = (
                    MonthlyStats.query.filter_by(statsYear=year)
                    .filter_by(statsMonth=month)
                    .filter_by(contactAccount=acct)
                    .first()
                )
                try:
                    if statsobj.contactMinutes < CONTACT_ACCT_REQS[acct]:
                        difference = CONTACT_ACCT_REQS[acct] - statsobj.contactMinutes
                        new_content += [
                            {
                                "date": get_first_meeting_day(month, year).strftime(
                                    DATEFMT
                                ),
                                "item": "HRS: Requires {} additional {} minutes.".format(
                                    difference, acct
                                ),
                            }
                        ]
                except AttributeError:
                    new_content += [
                        {
                            "date": datetime.strftime(
                                get_first_meeting_day(month, year), DATEFMT
                            ),
                            "item": "HRS: Requires {} additional {} minutes.".format(
                                CONTACT_ACCT_REQS[acct], acct
                            ),
                        }
                    ]
            return new_content

        def empty_days_check(targetDate):
            new_content = []
            month = targetDate["month"]
            year = targetDate["year"]

            # Get list of dates in month
            allMeetingDates = get_meeting_dates_in_month(month, year)
            for meeting in allMeetingDates:
                eventobj = Event.query.filter_by(eventDate=meeting)
                if result_length(eventobj) == 0:
                    new_content += [
                        {"date": meeting, "item": "NEV: No events scheduled."}
                    ]
            return new_content

        def gaps_in_time_check(targetDate):
            new_content = []
            month = targetDate["month"]
            year = targetDate["year"]

            allMeetingDates = get_meeting_dates_in_month(month, year)

            for meeting in allMeetingDates:
                eventobj = (
                    Event.query.filter_by(eventDate=meeting)
                    .filter_by(isDeleted=0)
                    .order_by(Event.startTime)
                )
                query_length = result_length(eventobj)
                for i in range(0, query_length - 1):
                    if eventobj[i].stopTime != eventobj[i + 1].startTime:
                        msg = "GAP: Event from {} to {} has a gap prior to the following event.".format(
                            eventobj[i].startTime, eventobj[i].stopTime
                        )
                        new_content += [{"date": meeting, "item": msg}]
            return new_content

        def tbd_check(targetDate):
            new_content = []
            month = targetDate["month"]
            year = targetDate["year"]

            allMeetingDates = get_meeting_dates_in_month(month, year)

            for meeting in allMeetingDates:
                eventobj = (
                    Event.query.filter_by(eventDate=meeting)
                    .filter_by(isDeleted=0)
                    .order_by(Event.startTime)
                )
                query_length = result_length(eventobj)
                for i in range(0, query_length):
                    if "TBD" in eventobj[i].eventName:
                        msg = "TBD: Event '{}' has an event name to be determined.".format(
                            eventobj[i].eventName
                        )
                        new_content += [{"date": meeting, "item": msg}]
                    if "TBD" in eventobj[i].eventLdr:
                        msg = "TBD: Event '{}' has an event leader to be determined.".format(
                            eventobj[i].eventName
                        )
                        new_content += [{"date": meeting, "item": msg}]
            return new_content

        def scheduled_check():
            new_content = []
            next_meet = datetime.today()
            next_meeting_dates = []
            while next_meet.weekday() != DAYNUM[meetingDay]:
                next_meet += timedelta(days=1)
            for week in range(0, 2):
                offset = 7 * week
                next_meeting_dates += [next_meet + timedelta(days=offset)]
            for meeting in next_meeting_dates:
                meeting_date = meeting.strftime(DATEFMT)
                eventobj = (
                    Event.query.filter_by(eventDate=meeting_date)
                    .filter_by(isDeleted=0)
                    .order_by(Event.startTime)
                )
                for n in range(0, result_length(eventobj)):
                    msg = ""
                    missing_flag_list = []
                    missing_flag_str = ""
                    event_name = ""
                    event_name = eventobj[n].eventName
                    if eventobj[n].isAgreedTo != 1:
                        missing_flag_list += ["isAgreedTo"]
                    if eventobj[n].isEmailScheduled != 1:
                        missing_flag_list += ["isEmailScheduled"]
                    if eventobj[n].isOnSiteViz != 1:
                        missing_flag_list += ["isOnSiteViz"]
                    for n in range(0, len(missing_flag_list)):
                        if n != len(missing_flag_list):
                            missing_flag_str += "{}, ".format(missing_flag_list[n])
                        else:
                            missing_flag_str += "and {} ".format(missing_flag_list[n])
                    if len(missing_flag_list) > 0:
                        msg += "FLG: {} flags are missing from event '{}'".format(
                            missing_flag_str, event_name
                        )
                        new_content += [{"date": meeting_date, "item": msg}]
            return new_content

        def received_check():
            new_content = []
            next_meet = datetime.today()
            next_meeting_dates = []
            while next_meet.weekday() != DAYNUM[meetingDay]:
                next_meet += timedelta(days=1)
            for week in range(0, 1):
                offset = 7 * week
                next_meeting_dates += [next_meet + timedelta(days=offset)]
            for meeting in next_meeting_dates:
                meeting_date = meeting.strftime(DATEFMT)
                eventobj = (
                    Event.query.filter_by(eventDate=meeting_date)
                    .filter_by(isDeleted=0)
                    .order_by(Event.startTime)
                )
                for n in range(0, result_length(eventobj)):
                    msg = ""
                    missing_flag_list = []
                    missing_flag_str = ""
                    event_name = ""
                    event_name = eventobj[n].eventName
                    if eventobj[n].isEmailConfirmed != 1:
                        missing_flag_list += ["isEmailConfirmed"]
                    for n in range(0, len(missing_flag_list)):
                        if n != len(missing_flag_list):
                            missing_flag_str += "{}, ".format(missing_flag_list[n])
                        else:
                            missing_flag_str += "and {} ".format(missing_flag_list[n])
                    if len(missing_flag_list) > 0:
                        msg += "FLG: {} flag missing from event '{}'".format(
                            missing_flag_str, event_name
                        )
                        new_content += [{"date": meeting_date, "item": msg}]
            return new_content

        def thanked_check():
            new_content = []
            msg = ""
            next_meet = datetime.today()
            while next_meet.weekday() != DAYNUM[meetingDay]:
                next_meet += timedelta(days=1)
            eventobj = Event.query.filter_by(isDeleted=0).filter_by(isEmailThanked=0)
            for n in range(0, result_length(eventobj)):
                if datetime.strptime(eventobj[n].eventDate, DATEFMT) < next_meet:
                    msg = "TYVM: Send thank you note to {} for {}".format(
                        eventobj[n].eventLdr, eventobj[n].eventName
                    )
                    new_content += [{"date": eventobj[n].eventDate, "item": msg}]
            return new_content

        # Begin main todo page logic

        # Things to report on:
        # [X] Months out to three months in advance that are short on contact hours
        # [X] Days out to three months that do not have events scheduled at all
        # [x] Days which have gaps or overlaps in the schedule, where ending time of previous does not match start time of next.
        # [X] Events with TBD in either the Event Name or Event Leader
        # [X] Events within two weeks that are not checked through Scheduled
        # [X] Events within one week that are not checked through Received
        # [X] Events that have occurred that do not have a thank you checked.
        # [ ] Days out to three months that are not up on siteviz

        # Get months and year of next three months.
        target_dates = get_target_dates()

        for each in target_dates:
            tmp_content += contact_hour_check(each)
            tmp_content += empty_days_check(each)
            tmp_content += gaps_in_time_check(each)
            tmp_content += tbd_check(each)
            tmp_content += scheduled_check()
            # Bubblesort listItems by the 'date'
            n = len(tmp_content)
            for i in range(n - 1):
                for j in range(0, n - i - 1):
                    if datetime.strptime(
                        tmp_content[j]["date"], DATEFMT
                    ) > datetime.strptime(tmp_content[j + 1]["date"], DATEFMT):
                        tmp_content[j], tmp_content[j + 1] = (
                            tmp_content[j + 1],
                            tmp_content[j],
                        )
            listItems += [tmp_content]
            listMonths += [MONTHNUM[each["month"]]]
            tmp_content = []

        tmp_notices = thanked_check()
        n = len(tmp_notices)
        for i in range(n - 1):
            for j in range(0, n - i - 1):
                if datetime.strptime(
                    tmp_notices[j]["date"], DATEFMT
                ) > datetime.strptime(tmp_notices[j + 1]["date"], DATEFMT):
                    tmp_notices[j], tmp_notices[j + 1] = (
                        tmp_notices[j + 1],
                        tmp_notices[j],
                    )
        listNotices += tmp_notices
        listMonths += ["Notices"]

        return render_template(
            "frame.html",
            items=listItems,
            months=listMonths,
            notices=listNotices,
            frametarget=frametarget,
        )
    else:
        frametarget = "blank"
        return render_template("frame.html", frametarget=frametarget)


if __name__ == "__main__":
    # app.run(debug=True, host="0.0.0.0")
    manager.run()
