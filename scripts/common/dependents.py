import logging
import re
import threading
import time

import requests
from bs4 import BeautifulSoup

from common import github_api

logger = logging.getLogger(__name__)

_NUMBER_RE = re.compile(r"(\d[\d,.]*)\s*(k)?\s*(?:Repositories|Used by)", re.IGNORECASE)

# /network/dependents はAPIではなく通常のWebページで、collect.pyの30並列
# スレッドプールと同じ同時実行数でアクセスすると同一IPからの高頻度アクセス
# とみなされ429が多発する(実測: 5,518件中4,191件が429)。ここだけ別に
# 同時接続数を絞る。8は暫定値。ログ(429の件数)を見ながら調整する。
# ponytail: 固定値、実行時間とのバランスで再調整が必要になったら変える
MAX_CONCURRENT_REQUESTS = 8
_semaphore = threading.Semaphore(MAX_CONCURRENT_REQUESTS)


class RepoGoneError(Exception):
    """dependentsページが404を返した(削除・非公開化・移動済みで、リトライしても復活しない)。"""


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
            with _semaphore:
                resp = requests.get(url, headers=headers, timeout=10)
        except requests.RequestException as exc:
            logger.warning("dependents fetch failed for %s/%s: %s", owner, repo, exc)
            time.sleep(2 ** attempt)
            continue

        if resp.status_code == 200:
            try:
                count = parse_dependents_count(resp.text)
            except Exception:
                logger.warning("dependents parse raised an exception for %s/%s", owner, repo)
                return None
            if count is None:
                logger.warning("dependents parse failed for %s/%s", owner, repo)
            return count

        if resp.status_code == 404:
            # 同じURLをリトライしても復活しないので即座に諦める
            raise RepoGoneError(f"{owner}/{repo} not found (404)")

        wait = github_api.rate_limit_wait_seconds(resp, attempt)
        logger.warning(
            "dependents fetch got status %s for %s/%s: waiting %.1fs",
            resp.status_code, owner, repo, wait,
        )
        time.sleep(wait)

    return None
