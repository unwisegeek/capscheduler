from picotui.context import Context
from picotui.screen import Screen
from picotui.widgets import *
from picotui.defs import *
import os
from datetime import date, datetime, timedelta


MONTHS = {
    1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr',
    5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug',
    9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec',
    13: 'All'
}

def monthnum(m):
    for i in range(1, len(MONTHS)):
        if m == MONTHS[i]:
            return i
    raise Exception("Unable to convert month to integer.")


def get_screen_geometry():
    """
    Function that takes no arguments.

    Returns two integers representing current terminal columns and current terminal rows.
    """
    try:
        term_columns, term_rows = os.get_terminal_size(0)
    except OSError:
        term_columns, term_rows = os.get_terminal_size(1)
    return term_columns, term_rows

def getdatesbyday(day, month, year):
    """
    Returns a list of dates for days.

    Arguments:

    day - Numerical day, with 0 being Sunday and 6 being Saturday.
    month - Numerical month, with 1 being January and 12 being December.
    year - Four digit year
    """
    results = []
    if 0 < month < 13:
        testdate = date(year, month, 1)
        while testdate.month == month:
            if testdate.weekday() == day:
                yield testdate
                #results += [ testdate ]
                testdate += timedelta(days=7)
            else: 
                testdate += timedelta(days=1)
        return results
    if month == 13:
        testdate = date(year, 1, 1)
        while testdate.year() == year:
            if testdate.weekday() == day:
                results += [ testdate ]
            testdate += timedelta(days=7)
        return results
    return [ '9999-09-09' ]

s = Screen()
t = datetime.now()
mc, mr = get_screen_geometry()

# Date Selections Box
with Context():
    s.attr_color(C_WHITE, C_BLUE)
    s.cls()
    s.attr_reset()

    # Create the main dialog window
    d = Dialog(1, 1, mc - 2, mr - 3, "CAP Scheduler")

    # Set the Year
    d.add(2, 2, " Year: ") 
    year_items = []
    for each in [ 0, -2, -1, 0, 1, 2 ]:
        year_items += [ str(t.year + each) ]
    year_listbox = WListBox(4, 1, year_items)
    d.add(9, 2, year_listbox)

    # Set the Month
    d.add(2, 3, "Month: ")
    month_items = [ " " + MONTHS[t.month] ]
    for i in range(1, len(MONTHS) + 1):
        month_items += [ " " + MONTHS[i] ]
    month_listbox = WListBox(4, 1, month_items)
    d.add(9, 3, month_listbox)

    # Write the meeting dates out in the panel.
    # dates_items

    target_year = int(year_listbox.get_cur_line())
    target_month = monthnum(month_listbox.get_cur_line().strip(' '))

    d.add(2, 4, "-----------")
    for each in range(2, mr - 5):
        d.add(16, each, '|')
        d.add(mc * .3, each, '|')
        d.add(mc * .7, each, '|')

    def update_date_list():
        date_items = []
        for i in getdatesbyday(4, target_month, target_year):
            date_items += [ i.strftime('%m-%d-%Y') ]
        date_listbox = WListBox(10, mr - 9, date_items)
        d.add(2, 5, date_listbox)

    update_date_list()

    # Handle year and month changes
    def year_changed(w):
        update_date_list()
        d.redraw()

    def month_changed(w):
        update_date_list()
        d.redraw()
    
    year_listbox.on("changed", year_changed)
    month_listbox.on("changed", month_changed)

    res = d.loop()