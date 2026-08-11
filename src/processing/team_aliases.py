"""Team name resolution against config/team_aliases.yaml (see
docs/data_ingestion.md section 4.3, "Normalize", and
docs/environment_configuration.md section 6).
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import yaml

from src.utils.config import PROJECT_ROOT

DEFAULT_ALIASES_PATH = PROJECT_ROOT / "config" / "team_aliases.yaml"


class UnknownTeamAliasError(ValueError):
    """Raised when a raw source team name has no entry in team_aliases.yaml.

    Deliberately not swallowed or defaulted: an unrecognised name is far
    more likely to be a new source-specific spelling than a genuinely new
    club, and silently creating a Team row for it would fragment that
    team's match history across two rows (see
    docs/testing_strategy.md section 3.1).
    """


class TeamAliasEntry(NamedTuple):
    canonical_key: str
    display_name: str


def load_alias_map(path: Path | None = None) -> dict[str, TeamAliasEntry]:
    """Load config/team_aliases.yaml into a flat {normalized_name: entry}
    lookup, case- and whitespace-insensitive on the raw name."""
    aliases_path = path or DEFAULT_ALIASES_PATH
    if not aliases_path.exists():
        raise FileNotFoundError(
            f"Team alias file not found at {aliases_path}. "
            "See docs/environment_configuration.md section 6."
        )
    with aliases_path.open("r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f) or {}

    alias_map: dict[str, TeamAliasEntry] = {}
    for canonical_key, entry in raw_config.items():
        display_name = entry["display_name"]
        for alias in entry.get("aliases", []):
            key = _normalize_lookup_key(alias)
            existing = alias_map.get(key)
            if existing is not None and existing.canonical_key != canonical_key:
                raise ValueError(
                    f"Alias {alias!r} in {aliases_path} is mapped to both "
                    f"{existing.canonical_key!r} and {canonical_key!r}."
                )
            alias_map[key] = TeamAliasEntry(canonical_key, display_name)
    return alias_map


def _normalize_lookup_key(name: str) -> str:
    return " ".join(name.strip().lower().split())


def resolve_team_alias(
    raw_name: str, alias_map: dict[str, TeamAliasEntry]
) -> TeamAliasEntry:
    """Resolve a raw source team name to its canonical key and display name."""
    entry = alias_map.get(_normalize_lookup_key(raw_name))
    if entry is None:
        raise UnknownTeamAliasError(
            f"No team alias entry for {raw_name!r}. Add it to "
            "config/team_aliases.yaml before re-running ingestion."
        )
    return entry
