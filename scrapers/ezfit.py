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
    return scrape_ezfit_range(
        studio,
        datetime.now(tz=MEXICO_TZ).date() - timedelta(days=HISTORY_DAYS),
        datetime.now(tz=MEXICO_TZ).date() + timedelta(days=FORECAST_DAYS),
    )


def scrape_ezfit_range(studio: dict, start: date, end: date) -> list[dict]:
    scraped_at = datetime.now(tz=MEXICO_TZ)
    scraped_date = scraped_at.date().isoformat()

    snapshots = []
    for day in _date_range(start, end):
        classes, spot_data = _fetch_schedule(studio, day)
        for class_ in classes:
            spots = spot_data.get(class_["schdl_id"]) or spot_data.get(str(class_["schdl_id"]))
            snapshots.append(_map_class(studio, class_, spots, scraped_at, scraped_date))
    return snapshots


def _date_range(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def _fetch_schedule(studio: dict, day: date) -> tuple[list[dict], dict]:
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
        return [], {}
    response.raise_for_status()
    payload = response.json()
    # spot_data trae aforo y reservas de TODAS las clases del día en la misma
    # respuesta — no hace falta llamar booked-spots/spots por separado.
    return payload.get("data") or [], payload.get("spot_data") or {}


def _map_class(
    studio: dict, class_: dict, spots: list[dict] | None, scraped_at: datetime, scraped_date: str
) -> dict:
    schdl_id = class_["schdl_id"]
    spot = (spots or [{}])[0]
    capacity = spot.get("total_spots")
    reserved = spot.get("booked_spots")
    available = spot.get("spots_left")
    occupancy_pct = round(reserved / capacity * 100, 2) if capacity else None

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
        "blocked": 0,
        "occupancy_pct": occupancy_pct,
        "apparent_occupancy_pct": occupancy_pct,
        "platform": "ezfit",
        "raw_class_id": str(schdl_id),
    }
