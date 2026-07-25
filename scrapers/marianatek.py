from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

MEXICO_TZ = ZoneInfo("America/Mexico_City")
FORECAST_DAYS = 7


def scrape_marianatek(studio: dict) -> list[dict]:
    scraped_at = datetime.now(tz=MEXICO_TZ)
    scraped_date = scraped_at.date().isoformat()
    today = scraped_at.date()
    end = today + timedelta(days=FORECAST_DAYS)

    classes = _fetch_classes(studio, today, end)

    snapshots = []
    for class_ in classes:
        # Clases pasadas devuelven capacity: 0 — se descartan (limitación conocida de Mariana Tek)
        if not class_.get("capacity"):
            continue
        snapshots.append(_map_class(studio, class_, scraped_at, scraped_date))
    return snapshots


def _fetch_classes(studio: dict, start: date, end: date) -> list[dict]:
    namespace = studio["namespace"]
    url = f"https://{namespace}.marianatek.com/api/customer/v1/classes"
    headers = {
        "Accept": "application/json",
        "Origin": f"https://{namespace}.marianaiframes.com",
        "Referer": f"https://{namespace}.marianaiframes.com/",
    }
    params = {
        "min_start_date": start.isoformat(),
        "max_start_date": end.isoformat(),
        "page_size": 500,
        "location": studio["location_id"],
    }

    results = []
    response = requests.get(url, params=params, headers=headers, timeout=20)
    response.raise_for_status()
    payload = response.json()
    results.extend(payload["results"])

    next_url = payload.get("next")
    while next_url:
        response = requests.get(next_url, headers=headers, timeout=20)
        response.raise_for_status()
        payload = response.json()
        results.extend(payload["results"])
        next_url = payload.get("next")

    return results


def _map_class(
    studio: dict, class_: dict, scraped_at: datetime, scraped_date: str
) -> dict:
    start_local = datetime.fromisoformat(
        class_["start_datetime"].replace("Z", "+00:00")
    ).astimezone(MEXICO_TZ)

    capacity = class_.get("capacity")
    available = class_.get("available_spot_count")
    reserved = capacity - available
    occupancy_pct = round(reserved / capacity * 100, 2)

    instructors = class_.get("instructors") or []
    coach = instructors[0]["name"] if instructors else None

    return {
        "studio_id": studio["id"],
        "scraped_at": scraped_at.isoformat(),
        "scraped_date": scraped_date,
        "class_date": start_local.date().isoformat(),
        "class_time": start_local.time().isoformat(timespec="seconds"),
        "class_name": (class_.get("class_type") or {}).get("name"),
        "coach": coach,
        "location_name": (class_.get("classroom") or {}).get("name"),
        "capacity": capacity,
        "reserved": reserved,
        "available": available,
        # Mariana Tek no distingue bloqueos de reservas como BUQ: todo lo no disponible es "reserved"
        "blocked": 0,
        "occupancy_pct": occupancy_pct,
        "apparent_occupancy_pct": occupancy_pct,
        "platform": "marianatek",
        "raw_class_id": str(class_["id"]),
    }
