from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

EZFIT_API_BASE = "https://api.ezfit.io/index.php/embed/api"
MEXICO_TZ = ZoneInfo("America/Mexico_City")
HISTORY_DAYS = 7
FORECAST_DAYS = 7

_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "*/*",
    "X-Requested-With": "XMLHttpRequest",
}


def scrape_ezfit(studio: dict) -> list[dict]:
    scraped_at = datetime.now(tz=MEXICO_TZ)
    scraped_date = scraped_at.date().isoformat()
    today = scraped_at.date()

    snapshots = []
    for day in _date_range(today - timedelta(days=HISTORY_DAYS), today + timedelta(days=FORECAST_DAYS)):
        for class_ in _fetch_schedule(studio, day):
            snapshots.append(_map_class(studio, class_, scraped_at, scraped_date))
    return snapshots


def _date_range(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def _fetch_schedule(studio: dict, day: date) -> list[dict]:
    response = requests.post(
        f"{EZFIT_API_BASE}/schedule",
        headers=_HEADERS,
        data={
            "gym_id": studio["gym_id"],
            "branch_id": studio["branch_id"],
            "class_date": f"{day.year}-{day.month}-{day.day}",
            "class_id": "",
            "employee_id": "",
        },
        timeout=20,
    )
    # Un día sin clases regresa 400 ("Schedule not found on this date") en vez
    # de una lista vacía con 200 — es el comportamiento normal de la API, no un error.
    if response.status_code == 400:
        return []
    response.raise_for_status()
    payload = response.json()
    return payload.get("data") or []


def _fetch_reserved(studio: dict, schdl_id: str) -> int:
    response = requests.post(
        f"{EZFIT_API_BASE}/booked-spots",
        headers=_HEADERS,
        data={"schdl_id": schdl_id, "gym_id": studio["gym_id"]},
        timeout=20,
    )
    response.raise_for_status()
    return response.json().get("pager", {}).get("total", 0)


def _fetch_capacity_and_blocked(studio: dict, class_: dict) -> tuple[int, int]:
    response = requests.post(
        f"{EZFIT_API_BASE}/spots",
        headers=_HEADERS,
        data={
            "class_id": class_["class_id"],
            "room_id": class_["room_id"],
            "schdl_id": class_["schdl_id"],
            "gym_id": studio["gym_id"],
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    capacity = len(payload.get("data") or [])
    blocked = len(payload.get("blocked_spot") or [])
    return capacity, blocked


def _map_class(studio: dict, class_: dict, scraped_at: datetime, scraped_date: str) -> dict:
    schdl_id = class_["schdl_id"]
    reserved = _fetch_reserved(studio, schdl_id)
    capacity, blocked = _fetch_capacity_and_blocked(studio, class_)
    available = capacity - reserved - blocked if capacity else None

    if capacity:
        occupancy_pct = round(reserved / capacity * 100, 2)
        apparent_occupancy_pct = round((reserved + blocked) / capacity * 100, 2)
    else:
        occupancy_pct = None
        apparent_occupancy_pct = None

    coach = class_.get("emp_nick_name") or " ".join(
        filter(None, [class_.get("emp_first_name"), class_.get("emp_last_name")])
    ) or None

    return {
        "studio_id": studio["id"],
        "scraped_at": scraped_at.isoformat(),
        "scraped_date": scraped_date,
        "class_date": class_["class_date"],
        "class_time": class_["class_start_time"],
        "class_name": class_.get("class_name") or class_.get("class_description"),
        "coach": coach,
        "location_name": class_.get("room_name") or studio["name"],
        "capacity": capacity,
        "reserved": reserved,
        "available": available,
        "blocked": blocked,
        "occupancy_pct": occupancy_pct,
        "apparent_occupancy_pct": apparent_occupancy_pct,
        "platform": "ezfit",
        "raw_class_id": str(schdl_id),
    }
