from common import github_api


def test_extract_owner_repo_from_search_item_valid():
    item = {"full_name": "modelcontextprotocol/servers"}
    assert github_api.extract_owner_repo_from_search_item(item) == ("modelcontextprotocol", "servers")


def test_extract_owner_repo_from_search_item_missing_full_name():
    assert github_api.extract_owner_repo_from_search_item({}) is None


def test_extract_owner_repo_from_search_item_malformed():
    assert github_api.extract_owner_repo_from_search_item({"full_name": "no-slash"}) is None
