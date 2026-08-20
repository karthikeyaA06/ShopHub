from datetime import timedelta

IST_OFFSET = timedelta(hours=5, minutes=30)


def to_ist(utc_dt):
    """Converts a naive UTC datetime (as stored by datetime.utcnow()) to IST."""
    if utc_dt is None:
        return None
    return utc_dt + IST_OFFSET


def format_ist(utc_dt, fmt="%d %b %Y, %I:%M %p", suffix=""):
    """Formats a stored UTC datetime as an IST string for display, e.g. on bills."""
    ist_dt = to_ist(utc_dt)
    if ist_dt is None:
        return "-"
    return ist_dt.strftime(fmt) + suffix
