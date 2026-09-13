from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

FITCO_API_BASE = "https://api.fitcoapp.net"
MEXICO_TZ = ZoneInfo("America/Mexico_City")
HISTORY_DAYS = 7
FORECAST_DAYS = 7


def scrape_fitco(studio: dict) -> list[dict]:
    scraped_at = datetime.now(tz=MEXICO_TZ)
    scraped_date = scraped_at.date().isoformat()
    today = scraped_at.date()
    start = today - timedelta(days=HISTORY_DAYS)
    end = today + timedelta(days=FORECAST_DAYS)

    lessons = _fetch_lessons(studio, start, end)

    snapshots = []
    for lesson in lessons:
        if not lesson.get("capacity"):
            continue
        snapshots.append(_map_lesson(studio, lesson, scraped_at, scraped_date))
    return snapshots


def _fetch_lessons(studio: dict, start: date, end: date) -> list[dict]:
    response = requests.get(
        f"{FITCO_API_BASE}/lessons/search",
        params={
            "from": f'"{start.isoformat()}"',
            "to": f'"{end.isoformat()}"',
            "establishmentId": studio["establishment_id"],
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["lessons"]


def _map_lesson(
    studio: dict, lesson: dict, scraped_at: datetime, scraped_date: str
) -> dict:
    capacity = lesson.get("capacity")
    reserved = lesson.get("reserves") or 0
    available = capacity - reserved
    occupancy_pct = round(reserved / capacity * 100, 2) if capacity else None

    instructors = lesson.get("instructors") or []
    coach = instructors[0].get("instructorName") if instructors else None

    return {
        "studio_id": studio["id"],
        "scraped_at": scraped_at.isoformat(),
        "scraped_date": scraped_date,
        "class_date": lesson["dateLesson"][:10],
        "class_time": lesson["startTime"],
        "class_name": lesson.get("name"),
        "coach": coach,
        "location_name": studio["name"],
        "capacity": capacity,
        "reserved": reserved,
        "available": available,
        "blocked": 0,
        "occupancy_pct": occupancy_pct,
        "apparent_occupancy_pct": occupancy_pct,
        "platform": "fitco",
        "raw_class_id": str(lesson["id"]),
    }
