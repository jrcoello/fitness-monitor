import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_KEY"]
        _client = create_client(url, key)
    return _client


def upsert_studios(studios: list[dict]) -> int:
    client = get_client()
    response = client.table("studios").upsert(studios, on_conflict="id").execute()
    return len(response.data)


def upsert_snapshots(snapshots: list[dict]) -> int:
    if not snapshots:
        return 0
    client = get_client()
    response = (
        client.table("snapshots")
        .upsert(snapshots, on_conflict="studio_id,raw_class_id,scraped_date")
        .execute()
    )
    return len(response.data)
