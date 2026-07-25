from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests

OLLYNK_API_BASE = "https://admin.ollynk.io/api"
MEXICO_TZ = ZoneInfo("America/Mexico_City")


def scrape_ollynk(studio: dict) -> list[dict]:
    scraped_at = datetime.now(tz=MEXICO_TZ)
    scraped_date = scraped_at.date().isoformat()

    class_names = _fetch_class_names(studio)
    sessions = _fetch_weekly_schedule(studio, scraped_at.date())

    return [
        _map_session(studio, session, class_names, scraped_at, scraped_date)
        for session in sessions
    ]


def _sdk_params(studio: dict) -> dict:
    return {
        "business_id": studio["business_id"],
        "branch_id": studio["branch_id"],
        "sdk_token": studio["sdk_token"],
    }


def _fetch_class_names(studio: dict) -> dict[str, str]:
    response = requests.get(
        f"{OLLYNK_API_BASE}/filter-list", params=_sdk_params(studio), timeout=15
    )
    response.raise_for_status()
    classes = response.json()["data"]["classes"]
    return {c["id"]: c["name"].strip() for c in classes}


def _fetch_weekly_schedule(studio: dict, start: date) -> list[dict]:
    response = requests.get(
        f"{OLLYNK_API_BASE}/schedules/weekly",
        params={**_sdk_params(studio), "startDate": start.isoformat()},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["data"]


def _map_session(
    studio: dict,
    session: dict,
    class_names: dict[str, str],
    scraped_at: datetime,
    scraped_date: str,
) -> dict:
    capacity = session.get("totalSpots")
    available = session.get("availableSpots")
    reserved = (
        capacity - available
        if capacity is not None and available is not None
        else None
    )
    occupancy_pct = round(reserved / capacity * 100, 2) if capacity else None
    coach = (session.get("coach") or {}).get("name")

    return {
        "studio_id": studio["id"],
        "scraped_at": scraped_at.isoformat(),
        "scraped_date": scraped_date,
        "class_date": session["date"],
        "class_time": f"{session['startTime']}:00",
        "class_name": class_names.get(session.get("classId"), session.get("classId")),
        "coach": coach,
        "location_name": session.get("roomName") or studio["name"],
        "capacity": capacity,
        "reserved": reserved,
        "available": available,
        "blocked": None,
        "occupancy_pct": occupancy_pct,
        "apparent_occupancy_pct": None,
        "platform": "ollynk",
        "raw_class_id": str(session["id"]),
    }
