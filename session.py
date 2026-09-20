import pandas as pd 

SESSION_TZ = "America/New_York"

def add_et_timestamp(data):
    data = data.copy()
    data["ts_event"] = pd.to_datetime(data["ts_event"], utc=True)
    data["ts_et"] = data["ts_event"].dt.tz_convert(SESSION_TZ)
    return data

def add_session_date(data):
    data = data.copy()
    local_time = data["ts_et"].dt.time
    after_18 = local_time >= pd.to_datetime("18:00:00").time()
    data["session_date"] = data["ts_et"].dt.date
    data.loc[after_18, "session_date"] = (
    data.loc[after_18, "ts_et"] + pd.Timedelta(days=1)
    ).dt.date

    return data

def add_session_label(data):
    data = data.copy()
    local_time = data["ts_et"].dt.time
    asia = (
        (local_time >= pd.to_datetime("20:00:00").time()) |
        (local_time < pd.to_datetime("00:00:00").time())
    )
    london = (
        (local_time >= pd.to_datetime("02:00:00").time()) &
        (local_time < pd.to_datetime("05:00:00").time())
    )
    ny_am = (
        (local_time >= pd.to_datetime("09:30:00").time()) &
        (local_time < pd.to_datetime("11:00:00").time())
    )
    ny_lunch = (
        (local_time >= pd.to_datetime("12:00:00").time()) &
        (local_time < pd.to_datetime("13:00:00").time())
    )
    ny_pm = (
        (local_time >= pd.to_datetime("13:30:00").time()) &
        (local_time < pd.to_datetime("16:00:00").time())
    )
    data["session_label"] = "Off"
    data.loc[asia, "session_label"] = "Asia"
    data.loc[london, "session_label"] = "London"
    data.loc[ny_am, "session_label"] = "NY AM"
    data.loc[ny_lunch, "session_label"] = "NY Lunch"
    data.loc[ny_pm, "session_label"] = "NY PM"
    return data
