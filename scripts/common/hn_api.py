import time
from datetime import datetime, timedelta, timezone

import requests

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"


def since_timestamp(reference: datetime, days_back: int = 1) -> int:
    since = reference - timedelta(days=days_back)
    return int(since.timestamp())


def count_daily_mentions(
    repo_full_name: str, reference: datetime | None = None, max_retries: int = 3
) -> int | None:
    if reference is None:
        reference = datetime.now(timezone.utc)

    params = {
        "query": repo_full_name,
        "numericFilters": f"created_at_i>{since_timestamp(reference)}",
    }

    for attempt in range(max_retries):
        try:
            resp = requests.get(ALGOLIA_URL, params=params, timeout=10)
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue

        if resp.status_code == 200:
            return len(resp.json().get("hits", []))
        time.sleep(2 ** attempt)

    return None
