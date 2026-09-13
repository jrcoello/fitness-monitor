from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

ATOMBOX_API_BASE = "https://api.atomboxcrm.com/v1.9/fitness-classes-v2"
MEXICO_TZ = ZoneInfo("America/Mexico_City")
HISTORY_DAYS = 7
FORECAST_DAYS = 7


def scrape_atombox(studio: dict) -> list[dict]:
    scraped_at = datetime.now(tz=MEXICO_TZ)
    scraped_date = scraped_at.date().isoformat()
    today = scraped_at.date()
    start = today - timedelta(days=HISTORY_DAYS)
    end = today + timedelta(days=FORECAST_DAYS)

    classes = _fetch_classes(studio, start, end)

    snapshots = []
    for class_ in classes:
        if class_.get("status") != "active" or not class_.get("capacity"):
            continue
        snapshots.append(_map_class(studio, class_, scraped_at, scraped_date))
    return snapshots


def _fetch_classes(studio: dict, start: date, end: date) -> list[dict]:
    permalink = studio["permalink"]
    response = requests.get(
        ATOMBOX_API_BASE,
        params={
            "branch_id": "",
            "date": f"{start.isoformat()}T06:00:00.000Z",
            "end_at": f"{end.isoformat()}T05:59:59.999Z",
            "permalink": permalink,
        },
        headers={
            "x-atom-schema": permalink,
            "x-atom-app-name": "atom-customers-landing-next",
            "x-atom-app-version": "0.1.1",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["fitnessClasses"]


def _map_class(studio: dict, class_: dict, scraped_at: datetime, scraped_date: str) -> dict:
    start_local = datetime.strptime(class_["start_at"], "%d-%m-%Y %H:%M")

    capacity = class_.get("capacity")
    available = class_.get("available_capacity") or 0
    reserved = capacity - available
    occupancy_pct = round(reserved / capacity * 100, 2) if capacity else None

    coach = (class_.get("coach") or {}).get("name")
    branch = (class_.get("branch") or {}).get("name") or studio["name"]

    return {
        "studio_id": studio["id"],
        "scraped_at": scraped_at.isoformat(),
        "scraped_date": scraped_date,
        "class_date": start_local.date().isoformat(),
        "class_time": start_local.time().isoformat(timespec="seconds"),
        "class_name": class_.get("title"),
        "coach": coach,
        "location_name": branch,
        "capacity": capacity,
        "reserved": reserved,
        "available": available,
        "blocked": 0,
        "occupancy_pct": occupancy_pct,
        "apparent_occupancy_pct": occupancy_pct,
        "platform": "atombox",
        "raw_class_id": str(class_["id"]),
    }
