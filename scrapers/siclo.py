from datetime import datetime
from zoneinfo import ZoneInfo

import requests

# Síclo migró de la v3 (numérica, requería login) a esta v7 (por slug de estudio,
# sin login) en algún punto entre el 9 de agosto y el 12 de septiembre de 2026 —
# la v3 seguía respondiendo 200 pero con "calendar": [] siempre, sin error, lo que
# dejó el scraper "funcionando" en silencio durante más de un mes sin traer datos.
SICLO_API_BASE = "https://api.siclo.com/api/v7"
MEXICO_TZ = ZoneInfo("America/Mexico_City")


def scrape_siclo(studio: dict) -> list[dict]:
    scraped_at = datetime.now(tz=MEXICO_TZ)
    scraped_date = scraped_at.date().isoformat()

    calendar = _fetch_calendar(studio)
    return [_map_class(studio, entry, scraped_at, scraped_date) for entry in calendar]


def _fetch_calendar(studio: dict) -> list[dict]:
    url = f"{SICLO_API_BASE}/studio/calendar-instructors/{studio['slug']}/"
    response = requests.get(
        url,
        params={"subscription": 0},
        headers={
            "ID-REGION": studio["region"],
            "X-Region-Id": studio["region"],
            "X-Country-Code": "MX",
            "Origin": "https://siclo.com",
            "Accept": "application/json",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["calendar"]


def _map_class(
    studio: dict, entry: dict, scraped_at: datetime, scraped_date: str
) -> dict:
    # "date" viene en UTC ("...Z"); se convierte a hora de Ciudad de México
    start_local = datetime.fromisoformat(
        entry["date"].replace("Z", "+00:00")
    ).astimezone(MEXICO_TZ)
    capacity = entry.get("total_bikes")
    available = entry.get("available_bikes")
    reserved = (capacity - available) if capacity is not None and available is not None else None
    occupancy_pct = round(reserved / capacity * 100, 2) if capacity else None

    instructors = entry.get("instructors") or []
    coach = instructors[0]["name"] if instructors else None

    return {
        "studio_id": studio["id"],
        "scraped_at": scraped_at.isoformat(),
        "scraped_date": scraped_date,
        "class_date": start_local.date().isoformat(),
        "class_time": start_local.time().isoformat(timespec="seconds"),
        "class_name": (entry.get("brand") or {}).get("name"),
        "coach": coach,
        "location_name": studio["name"],
        "capacity": capacity,
        "reserved": reserved,
        "available": available,
        "blocked": None,
        "occupancy_pct": occupancy_pct,
        "apparent_occupancy_pct": None,
        "platform": "siclo",
        "raw_class_id": str(entry["id_class"]),
    }
