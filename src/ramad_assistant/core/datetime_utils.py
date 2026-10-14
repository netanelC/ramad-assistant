"""Timezone and real-time Israeli datetime utilities."""
from datetime import datetime, timezone, timedelta
from typing import Optional
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore


ISRAEL_TIMEZONE_NAME = "Asia/Jerusalem"


def get_israel_now() -> datetime:
    """Returns the current aware datetime in Israel (Asia/Jerusalem)."""
    if ZoneInfo:
        try:
            return datetime.now(ZoneInfo(ISRAEL_TIMEZONE_NAME))
        except Exception:
            pass
    # Fallback to UTC+3 (Israel Daylight Time)
    return datetime.now(timezone(timedelta(hours=3)))


def get_current_datetime_context() -> str:
    """
    Returns an authoritative, natural Hebrew string representing the current date, day of week, and time.
    Injected into LLM system instructions to guarantee 100% temporal accuracy.
    """
    now = get_israel_now()
    days = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
    day_name = days[now.weekday()]
    months = [
        "", "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
        "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"
    ]
    month_name = months[now.month]

    return (
        f"📅 תאריך ושעה נוכחיים ומדויקים בישראל: יום {day_name}, {now.day} ב{month_name} {now.year}, שעה {now.strftime('%H:%M')}.\n"
        f"תאריך בפורמט ISO: {now.strftime('%Y-%m-%d %H:%M')}.\n"
        "חובה עליך להתבסס באופן בלעדי על מועד זה בכל שאלה על 'היום', 'מחר', תאריכים, ימי השבוע או תג\"בים!"
    )
