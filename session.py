import pandas as pd 
from config import (
    SESSION_TZ,SESSION_START,
    ASIA_START, ASIA_END,
    LONDON_START, LONDON_END,
    NY_AM_START, NY_AM_END,
    NY_LUNCH_START, NY_LUNCH_END,
    NY_PM_START, NY_PM_END
)

def add_et_timestamp(data):
    data = data.copy()
    data["ts_event"] = pd.to_datetime(data["ts_event"], utc=True)
    data["ts_et"] = data["ts_event"].dt.tz_convert(SESSION_TZ)
    return data

def add_session_date(data):
    data = data.copy()
    local_time = data["ts_et"].dt.time
    after_18 = local_time >= pd.to_datetime(SESSION_START).time()
    data["session_date"] = data["ts_et"].dt.date
    data.loc[after_18, "session_date"] = (
    data.loc[after_18, "ts_et"] + pd.Timedelta(days=1)
    ).dt.date

    return data

def add_session_label(data):
    data = data.copy()
    local_time = data["ts_et"].dt.time
    asia = (
        # Asia wraps past midnight, so either side of midnight is included.
        (local_time >= pd.to_datetime(ASIA_START).time()) |
        (local_time < pd.to_datetime(ASIA_END).time())
    )
    london = (
        (local_time >= pd.to_datetime(LONDON_START).time()) &
        (local_time < pd.to_datetime(LONDON_END).time())
    )
    ny_am = (
        (local_time >= pd.to_datetime(NY_AM_START).time()) &
        (local_time < pd.to_datetime(NY_AM_END).time())
    )
    ny_lunch = (
        (local_time >= pd.to_datetime(NY_LUNCH_START).time()) &
        (local_time < pd.to_datetime(NY_LUNCH_END).time())
    )
    ny_pm = (
        (local_time >= pd.to_datetime(NY_PM_START).time()) &
        (local_time < pd.to_datetime(NY_PM_END).time())
    )
    data["session_label"] = "Off"
    data.loc[asia, "session_label"] = "Asia"
    data.loc[london, "session_label"] = "London"
    data.loc[ny_am, "session_label"] = "NY AM"
    data.loc[ny_lunch, "session_label"] = "NY Lunch"
    data.loc[ny_pm, "session_label"] = "NY PM"
    return data
