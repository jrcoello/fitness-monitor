from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

BUQ_API_BASE = "https://buq.partners/api"
MEXICO_TZ = ZoneInfo("America/Mexico_City")
HISTORY_DAYS = 7


def scrape_buq(studio: dict, token: str) -> list[dict]:
    scraped_at = datetime.now(tz=MEXICO_TZ)
    scraped_date = scraped_at.date().isoformat()
    today = scraped_at.date()
    start = today - timedelta(days=HISTORY_DAYS)

    snapshots = []
    for location_id in studio["locations"]:
        meetings = _fetch_meetings(studio, token, location_id, start, today)
        for meeting in meetings:
            snapshots.append(_map_meeting(studio, meeting, scraped_at, scraped_date))
    return snapshots


def _fetch_meetings(
    studio: dict, token: str, location_id: int, start: date, end: date
) -> list[dict]:
    url = f"{BUQ_API_BASE}/brand/{studio['brand_slug']}/location/{location_id}/meetings"
    response = requests.get(
        url,
        params={
            "only_actives": "true",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "reducePopulation": "true",
        },
        headers={
            "Authorization": f"Bearer {token}",
            "gafafit-company": str(studio["company_id"]),
            "Origin": studio["origin"],
            "Accept": "application/json",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def _map_meeting(
    studio: dict, meeting: dict, scraped_at: datetime, scraped_date: str
) -> dict:
    # start_date viene en UTC ("...Z"); se convierte a la hora local de la propia clase.
    # No todos los estudios están en CDMX (hay en Cancún, Tijuana, Mérida, etc.), así que
    # se usa el campo "timezone" de cada clase en vez de asumir America/Mexico_City fijo —
    # los metadatos de zona horaria a nivel de marca en BUQ no son confiables (ej. un estudio
    # de Puerto Rico venía marcado como America/Mexico_City).
    class_tz = ZoneInfo(meeting.get("timezone") or "America/Mexico_City")
    start_local = datetime.fromisoformat(
        meeting["start_date"].replace("Z", "+00:00")
    ).astimezone(class_tz)
    capacity = meeting.get("capacity")
    reserved = meeting.get("reservation_count")
    available = meeting.get("available")

    # Algunos estudios (via GAFA) bloquean spots para Gympass/Totalpass y no los liberan
    # después de que la clase pasa. `available` ya los descuenta, `reservation_count` no:
    # capacity = reserved + available + blocked
    blocked_positions = (meeting.get("extra_fields") or {}).get("blocked_positions") or {}
    blocked = len(blocked_positions)

    if capacity:
        occupancy_pct = round(reserved / capacity * 100, 2)
        apparent_occupancy_pct = round((capacity - available) / capacity * 100, 2)
    else:
        occupancy_pct = None
        apparent_occupancy_pct = None

    return {
        "studio_id": studio["id"],
        "scraped_at": scraped_at.isoformat(),
        "scraped_date": scraped_date,
        "class_date": start_local.date().isoformat(),
        "class_time": start_local.time().isoformat(timespec="seconds"),
        "class_name": meeting.get("type"),
        "coach": meeting.get("title"),
        "location_name": (meeting.get("location") or {}).get("name"),
        "capacity": capacity,
        "reserved": reserved,
        "available": available,
        "blocked": blocked,
        "occupancy_pct": occupancy_pct,
        "apparent_occupancy_pct": apparent_occupancy_pct,
        "platform": "buq",
        "raw_class_id": str(meeting["id"]),
    }
