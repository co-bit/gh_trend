import time

import requests

API_BASE = "https://api.github.com"
MAX_SEARCH_PAGES = 10  # GitHub Search APIは最大1000件(100件×10ページ)まで


def extract_owner_repo_from_search_item(item: dict) -> tuple[str, str] | None:
    full_name = item.get("full_name", "")
    if "/" not in full_name:
        return None
    owner, repo = full_name.split("/", 1)
    if not owner or not repo:
        return None
    return owner, repo


def _headers(token: str | None) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _rate_limit_wait_seconds(resp, attempt: int) -> float:
    retry_after = resp.headers.get("Retry-After")
    if retry_after is not None:
        try:
            return min(float(retry_after), 65)
        except ValueError:
            pass

    reset = resp.headers.get("x-ratelimit-reset")
    if reset is not None:
        try:
            wait = int(reset) - time.time()
            if wait > 0:
                return min(wait, 65)
        except ValueError:
            pass

    return 2 ** attempt


def _request_with_retry(url: str, headers: dict, params: dict | None = None, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue

        if resp.status_code == 200:
            return resp
        if resp.status_code in (403, 429):
            time.sleep(_rate_limit_wait_seconds(resp, attempt))
            continue
        return None

    return None


def get_repo_stars(owner: str, repo: str, token: str | None = None) -> int | None:
    resp = _request_with_retry(f"{API_BASE}/repos/{owner}/{repo}", _headers(token))
    if resp is None:
        return None
    try:
        return resp.json().get("stargazers_count")
    except ValueError:
        return None


def get_repo_description(owner: str, repo: str, token: str | None = None) -> str | None:
    resp = _request_with_retry(f"{API_BASE}/repos/{owner}/{repo}", _headers(token))
    if resp is None:
        return None
    try:
        return resp.json().get("description")
    except ValueError:
        return None


def search_repos(query: str, token: str | None = None, per_page: int = 100) -> list[dict]:
    results = []
    for page in range(1, MAX_SEARCH_PAGES + 1):
        if page > 1:
            # GitHub Search API allows ~30 authenticated requests/min; a small
            # inter-page delay keeps a single keyword's pagination under that
            # limit instead of relying solely on reactive 403/429 backoff.
            time.sleep(2)

        resp = _request_with_retry(
            f"{API_BASE}/search/repositories",
            _headers(token),
            params={"q": query, "per_page": per_page, "page": page},
        )
        if resp is None:
            break

        try:
            items = resp.json().get("items", [])
        except ValueError:
            break

        for item in items:
            parsed = extract_owner_repo_from_search_item(item)
            if parsed is not None:
                results.append({"owner": parsed[0], "repo": parsed[1]})

        if len(items) < per_page:
            break

    return results
