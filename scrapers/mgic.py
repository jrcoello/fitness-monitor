from datetime import datetime
from zoneinfo import ZoneInfo

import requests

MEXICO_TZ = ZoneInfo("America/Mexico_City")


def scrape_mgic(studio: dict) -> list[dict]:
    scraped_at = datetime.now(tz=MEXICO_TZ)
    scraped_date = scraped_at.date().isoformat()

    classes = _fetch_classes(studio)

    snapshots = []
    for c in classes:
        room = c.get("room") or {}
        location_name = (room.get("studio") or {}).get("name")
        if location_name != studio["location_name"]:
            continue
        snapshots.append(_map_class(studio, c, scraped_at, scraped_date))
    return snapshots


def _fetch_classes(studio: dict) -> list[dict]:
    # Un solo GET sin auth regresa ~2 meses (pasado + futuro) de TODAS las sedes
    # del tenant — el filtro por sede se hace en scrape_mgic() comparando
    # room.studio.name, igual que hace wodify.py con locationId.
    response = requests.get(
        f"https://{studio['tenant']}.mgic.app/api/embed/classes",
        headers={"Accept": "application/json"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def _map_class(studio: dict, c: dict, scraped_at: datetime, scraped_date: str) -> dict:
    start_local = datetime.fromisoformat(
        c["startsAt"].replace("Z", "+00:00")
    ).astimezone(MEXICO_TZ)

    room = c.get("room") or {}
    capacity = room.get("maxCapacity")
    reserved = c.get("bookingsCount") or 0
    available = (capacity - reserved) if capacity is not None else None
    occupancy_pct = round(reserved / capacity * 100, 2) if capacity else None

    return {
        "studio_id": studio["id"],
        "scraped_at": scraped_at.isoformat(),
        "scraped_date": scraped_date,
        "class_date": start_local.date().isoformat(),
        "class_time": start_local.time().isoformat(timespec="seconds"),
        "class_name": (c.get("classType") or {}).get("name"),
        "coach": (c.get("coach") or {}).get("name"),
        "location_name": studio["location_name"],
        "capacity": capacity,
        "reserved": reserved,
        "available": available,
        "blocked": 0,
        "occupancy_pct": occupancy_pct,
        "apparent_occupancy_pct": occupancy_pct,
        "platform": "mgic",
        "raw_class_id": str(c["id"]),
    }
