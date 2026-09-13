import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

WODIFY_API_BASE = "https://app-api.wodify.com/Class_API/rest/internal"
MEXICO_TZ = ZoneInfo("America/Mexico_City")
HISTORY_DAYS = 7
FORECAST_DAYS = 7

_LOCATION_SUFFIX = re.compile(r"\s*\([^)]*\)\s*$")


def scrape_wodify(studio: dict) -> list[dict]:
    scraped_at = datetime.now(tz=MEXICO_TZ)
    scraped_date = scraped_at.date().isoformat()
    today = scraped_at.date()
    start = today - timedelta(days=HISTORY_DAYS)
    end = today + timedelta(days=FORECAST_DAYS)

    classes = _fetch_classes(studio, start, end)

    snapshots = []
    for class_ in classes:
        if class_.get("isCanceled") or class_.get("locationId") != studio["location_id"]:
            continue
        if not class_.get("classLimit"):
            continue
        snapshots.append(_map_class(studio, class_, scraped_at, scraped_date))
    return snapshots


def _fetch_classes(studio: dict, start, end) -> list[dict]:
    # El endpoint público no filtra por sede: regresa todas las ubicaciones del
    # mismo CustomerId. El filtro por locationId se hace en scrape_wodify().
    response = requests.get(
        f"{WODIFY_API_BASE}/GetClasses_ByInterval",
        params={
            "CustomerId": studio["customer_id"],
            "start": start.strftime("%m/%d/%Y"),
            "end": end.strftime("%m/%d/%Y"),
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def _map_class(studio: dict, class_: dict, scraped_at: datetime, scraped_date: str) -> dict:
    start_local = datetime.strptime(class_["start"], "%m/%d/%Y %H:%M:%S")

    capacity = class_.get("classLimit")
    reserved = class_.get("classReservations") or 0
    available = capacity - reserved
    occupancy_pct = round(reserved / capacity * 100, 2) if capacity else None

    class_name = _LOCATION_SUFFIX.sub("", class_.get("title") or "").strip()
    coach = class_.get("description") or None

    return {
        "studio_id": studio["id"],
        "scraped_at": scraped_at.isoformat(),
        "scraped_date": scraped_date,
        "class_date": start_local.date().isoformat(),
        "class_time": start_local.time().isoformat(timespec="seconds"),
        "class_name": class_name,
        "coach": coach,
        "location_name": studio["name"],
        "capacity": capacity,
        "reserved": reserved,
        "available": available,
        "blocked": 0,
        "occupancy_pct": occupancy_pct,
        "apparent_occupancy_pct": occupancy_pct,
        "platform": "wodify",
        "raw_class_id": str(class_["id"]),
    }
