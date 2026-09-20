import pandas as pd
from session import add_et_timestamp

DATA_PATH = r"C:\trading-data\project4\NQ-continuous-1m-adjusted.csv"

import pandas as pd
from session import add_et_timestamp, add_session_date , add_session_label

test = pd.DataFrame({
    "ts_event": [
        "2021-11-08 01:00:00+00:00",  # 20:00 Sun ET → ASIA
        "2021-11-08 04:59:00+00:00",  # 23:59 Sun ET → ASIA
        "2021-11-08 05:00:00+00:00",  # 00:00 Mon ET → ASIA
        "2021-11-08 07:00:00+00:00",  # 02:00 Mon ET → LONDON
        "2021-11-08 09:59:00+00:00",  # 04:59 Mon ET → LONDON
        "2021-11-08 10:00:00+00:00",  # 05:00 Mon ET → OFF
        "2021-11-08 14:30:00+00:00",  # 09:30 Mon ET → NY_AM
        "2021-11-08 16:59:00+00:00",  # 11:59 Mon ET → OFF
        "2021-11-08 17:00:00+00:00",  # 12:00 Mon ET → NY_LUNCH
        "2021-11-08 17:59:00+00:00",  # 12:59 Mon ET → NY_LUNCH
        "2021-11-08 18:00:00+00:00",  # 13:00 Mon ET → OFF
        "2021-11-08 18:30:00+00:00",  # 13:30 Mon ET → NY_PM
        "2021-11-08 20:59:00+00:00",  # 15:59 Mon ET → NY_PM
        "2021-11-08 21:00:00+00:00",  # 16:00 Mon ET → OFF
    ]
})

result = add_et_timestamp(test)
result = add_session_date(result)
result = add_session_label(result)

print(result[["ts_et", "session_date", "session_label"]])