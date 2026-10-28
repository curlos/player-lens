"""Shared test fixtures: the real hero match files, and a scratch data dir for anything that writes."""

from pathlib import Path

import pytest

from agents.inputs import build_plan, load_match

ROOT = Path(__file__).resolve().parent.parent
MATCH = "md38_title_decider"
STAR = "azc_09"


@pytest.fixture(scope="session")
def bundle():
    return load_match(ROOT / "data", MATCH)


@pytest.fixture(scope="session")
def plan():
    return build_plan(ROOT / "data", MATCH, STAR)


@pytest.fixture
def scratch(tmp_path):
    """A data dir whose matches are the real ones (symlinked) but whose commentary, audio and ledger are empty."""
    (tmp_path / "matches").symlink_to(ROOT / "data" / "matches", target_is_directory=True)
    return tmp_path
