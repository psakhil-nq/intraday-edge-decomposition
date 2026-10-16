SESSION_TZ = "America/New_York"
SESSION_START = "18:00"
TICK_SIZE = 0.25

ASIA_START = "20:00"
ASIA_END = "00:00"

LONDON_START = "02:00"
LONDON_END = "05:00"

NY_AM_START = "09:30"
NY_AM_END = "11:00"

NY_LUNCH_START = "12:00"
NY_LUNCH_END = "13:00"

NY_PM_START = "13:30"
NY_PM_END = "16:00"

QUALITY_REQUIRED_WINDOWS = ("London" , "NY AM")
QUALITY_MAX_MISSING_RUN = 2

# CP2B mechanical bias parameters
PROXY_A_LOOKBACK_HOURS = 24
FIB_BULLISH_THRESHOLD = 0.45
FIB_BEARISH_THRESHOLD = 0.55
FOUR_HOUR_SESSION_ANCHOR = "18:00"
FORCED_FLAT_END = "16:59"
ASIA_LONDON_PROXIMITY_NQ_POINTS = 50
ASIA_LONDON_PROXIMITY_ES_POINTS = 10
NY_AM_FIB_AVAILABLE_FROM = "10:00"

# Databento-degraded CME session dates mapped from the 14 degraded UTC
# dates documented in CP1. 2025-11-28 is included because it is an
# affected session even though CP1 eligibility excludes it.
DEGRADED_SESSION_DATES = (
    "2021-12-06",
    "2022-01-03",
    "2024-09-18",
    "2024-09-19",
    "2025-09-17",
    "2025-09-18",
    "2025-09-24",
    "2025-09-25",
    "2025-11-28",
    "2026-03-16",
    "2026-03-17",
    "2026-04-10",
    "2026-05-25",
    "2026-07-30",
    "2026-07-31",
)
