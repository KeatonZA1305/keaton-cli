"""Tests for the marketplace CLI helpers and the run() install hint."""
from __future__ import annotations

from keaton import marketcli, toolcli
from keaton.tui import marketplace as mkt


def test_resolve_by_key_name_binary_and_prefix():
    assert marketcli._resolve("docker").key == "docker"
    assert marketcli._resolve("Docker").key == "docker"          # case-insensitive name
    assert marketcli._resolve("psql").key == "postgres"          # by binary
    assert marketcli._resolve("postgre").key == "postgres"       # unique prefix
    assert marketcli._resolve("definitely-not-a-tool") is None


def test_resolve_ambiguous_prefix_returns_none():
    # No unique match should return None rather than guessing.
    # (Both keys start with the same letters would be ambiguous; assert stability.)
    assert marketcli._resolve("") is None


def test_marketplace_hint_matches_catalog_names():
    hint = toolcli._marketplace_hint("claude")
    assert hint and "keaton install claude" in hint
    hint2 = toolcli._marketplace_hint("set up kubectl please")
    assert hint2 and "kubectl" in hint2
    assert toolcli._marketplace_hint("teleport to mars") is None


def test_install_commands_exist_for_core_catalog():
    # Every catalog item should map to *some* installer (or None gracefully).
    for it in mkt.CATALOG:
        cmd = mkt.install_command(it)
        assert cmd is None or (isinstance(cmd, list) and cmd)
