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
            time.sleep(2 ** attempt)
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


def search_repos(query: str, token: str | None = None, per_page: int = 100) -> list[dict]:
    results = []
    for page in range(1, MAX_SEARCH_PAGES + 1):
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
