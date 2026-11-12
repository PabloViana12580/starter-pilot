import logging
import time


class UTCFormatter(logging.Formatter):
    """ISO 8601 timestamps in UTC (2026-01-31T09:15:02Z), whatever the server's time zone."""

    converter = time.gmtime
    default_time_format = '%Y-%m-%dT%H:%M:%S'
    default_msec_format = '%s.%03dZ'
