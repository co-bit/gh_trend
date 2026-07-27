import logging
import re
import time

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_NUMBER_RE = re.compile(r"(\d[\d,.]*)\s*(k)?\s*(?:Repositories|Used by)", re.IGNORECASE)


def parse_dependents_count(html: str) -> int | None:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    match = _NUMBER_RE.search(text)
    if not match:
        return None

    number_str, k_suffix = match.groups()
    number_str = number_str.replace(",", "")
    try:
        value = float(number_str)
    except ValueError:
        return None

    if k_suffix:
        value *= 1000
    return int(value)


def get_dependents_count(owner: str, repo: str, max_retries: int = 3) -> int | None:
    url = f"https://github.com/{owner}/{repo}/network/dependents"
    headers = {"User-Agent": "gh-trend-dashboard-bot/1.0"}

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=10)
        except requests.RequestException as exc:
            logger.warning("dependents fetch failed for %s/%s: %s", owner, repo, exc)
            time.sleep(2 ** attempt)
            continue

        if resp.status_code == 200:
            count = parse_dependents_count(resp.text)
            if count is None:
                logger.warning("dependents parse failed for %s/%s", owner, repo)
            return count

        logger.warning("dependents fetch got status %s for %s/%s", resp.status_code, owner, repo)
        time.sleep(2 ** attempt)

    return None
