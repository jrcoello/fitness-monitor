import argparse
import json
from pathlib import Path

from core.supabase_client import upsert_snapshots, upsert_studios
from core.token_manager import get_buq_token, get_siclo_token
from scrapers.buq import scrape_buq
from scrapers.marianatek import scrape_marianatek
from scrapers.ollynk import scrape_ollynk
from scrapers.siclo import scrape_siclo

STUDIOS_PATH = Path(__file__).resolve().parent.parent / "config" / "studios.json"


def load_studios(platform: str | None = None, studio_id: str | None = None) -> list[dict]:
    with open(STUDIOS_PATH) as f:
        studios = json.load(f)["studios"]

    studios = [s for s in studios if s.get("active", True)]
    if platform:
        studios = [s for s in studios if s["platform"] == platform]
    if studio_id:
        studios = [s for s in studios if s["id"] == studio_id]
    return studios


def _studio_record(studio: dict) -> dict:
    return {
        "id": studio["id"],
        "name": studio["name"],
        "platform": studio["platform"],
        "city": studio.get("city"),
        "neighborhood": None,
        "brand_slug": studio.get("brand_slug"),
        "company_id": studio.get("company_id"),
        "namespace": studio.get("namespace"),
        "location_id": studio.get("location_id"),
        "active": studio.get("active", True),
    }


def run(platform: str | None = None, studio_id: str | None = None, dry_run: bool = False) -> None:
    studios = load_studios(platform, studio_id)

    if not dry_run and studios:
        upsert_studios([_studio_record(s) for s in studios])

    buq_token = get_buq_token() if any(s["platform"] == "buq" for s in studios) else None
    siclo_token = get_siclo_token() if any(s["platform"] == "siclo" for s in studios) else None

    for studio in studios:
        try:
            if studio["platform"] == "buq":
                snapshots = scrape_buq(studio, buq_token)
            elif studio["platform"] == "marianatek":
                snapshots = scrape_marianatek(studio)
            elif studio["platform"] == "siclo":
                snapshots = scrape_siclo(studio, siclo_token)
            elif studio["platform"] == "ollynk":
                snapshots = scrape_ollynk(studio)
            else:
                print(f"{studio['name']}: plataforma desconocida '{studio['platform']}'")
                continue

            print(f"{studio['name']}: {len(snapshots)} clases encontradas")

            if not dry_run:
                saved = upsert_snapshots(snapshots)
                print(f"{studio['name']}: {saved} clases guardadas")

        except Exception as e:
            print(f"ERROR {studio['name']}: {e}")
            continue


def main() -> None:
    parser = argparse.ArgumentParser(description="Fitness Monitor Engine — runner")
    parser.add_argument("--platform", choices=["buq", "marianatek", "siclo", "ollynk"])
    parser.add_argument("--studio")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run(platform=args.platform, studio_id=args.studio, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
