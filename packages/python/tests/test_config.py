from cleanedweb_mcp import CATALOG_URL, PUBLIC_URL, resolve_config


def test_public_profile_and_hint_without_key():
    c = resolve_config({})
    assert c.url == PUBLIC_URL
    assert c.api_key is None
    assert "CLEANEDWEB_API_KEY" in c.hint


def test_catalog_profile_with_key_and_no_hint():
    c = resolve_config({"CLEANEDWEB_API_KEY": " cw_key "})
    assert c.url == CATALOG_URL
    assert c.api_key == "cw_key"
    assert c.hint is None


def test_empty_and_placeholder_values_are_unset():
    assert resolve_config({"CLEANEDWEB_API_KEY": ""}).api_key is None
    assert resolve_config({"CLEANEDWEB_API_KEY": "${user_config.api_key}"}).url == PUBLIC_URL
    assert resolve_config({"CLEANEDWEB_MCP_URL": "  "}).url == PUBLIC_URL


def test_url_override():
    c = resolve_config({"CLEANEDWEB_API_KEY": "k", "CLEANEDWEB_MCP_URL": "http://localhost:9/mcp"})
    assert c.url == "http://localhost:9/mcp"
