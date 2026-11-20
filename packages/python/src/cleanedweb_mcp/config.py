"""Where the proxy connects and how it signs in, decided from the environment."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass

CATALOG_URL = "https://api.cleanedweb.com/mcp?profile=catalog"
PUBLIC_URL = "https://api.cleanedweb.com/mcp?profile=public"

_PLACEHOLDER = re.compile(r"^\$\{[^}]*\}$")


@dataclass(frozen=True)
class Config:
    url: str
    """Hosted MCP endpoint the proxy forwards to."""
    api_key: str | None = None
    """API key sent as `Authorization: Bearer`, if any."""
    hint: str | None = None
    """One-line stderr hint to print at start-up, if any."""


def _clean(value: str | None) -> str | None:
    """An env value counts as set only when it holds text (not empty, not an unresolved `${...}`)."""
    v = (value or "").strip()
    if not v or _PLACEHOLDER.match(v):
        return None
    return v


def resolve_config(env: Mapping[str, str] | None = None) -> Config:
    env = os.environ if env is None else env
    api_key = _clean(env.get("CLEANEDWEB_API_KEY"))
    override = _clean(env.get("CLEANEDWEB_MCP_URL"))
    url = override or (CATALOG_URL if api_key else PUBLIC_URL)
    hint = None
    if not api_key:
        hint = (
            "cleanedweb-mcp: no CLEANEDWEB_API_KEY set; only find_api and get_api work. "
            "Create a key with the read and run scopes at https://app.cleanedweb.com/ to run APIs."
        )
    return Config(url=url, api_key=api_key, hint=hint)
