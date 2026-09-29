import datetime

# O'zbekiston vaqti (UTC+5, yozgi vaqt yo'q)
LOCAL_TZ = datetime.timezone(datetime.timedelta(hours=5))


def fmt_date(value: datetime.datetime) -> str:
    return value.astimezone(LOCAL_TZ).strftime("%d.%m.%Y %H:%M")
