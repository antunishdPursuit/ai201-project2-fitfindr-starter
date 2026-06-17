"""
tests/test_tools.py

Isolated tests for the three FitFindr tools (Milestone 3).
At least one test per failure mode.

Run with:  pytest tests/
"""

import pytest

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings (no LLM, runs offline) ─────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    # Failure mode: nothing matches → empty list, not an exception.
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter_case_insensitive():
    # "m" should match listings whose size contains "M" (e.g. "S/M", "M/L").
    results = search_listings("top", size="m", max_price=None)
    assert all("m" in str(item["size"]).lower() for item in results)


def test_search_sorted_by_relevance():
    results = search_listings("graphic tee", size=None, max_price=None)
    # The most on-topic listing should surface first.
    assert "tee" in results[0]["title"].lower() or "graphic" in (
        " ".join(results[0]["style_tags"]).lower()
    )


# ── create_fit_card failure mode (no LLM call needed) ──────────────────────────

_SAMPLE_ITEM = {
    "title": "Graphic Tee — 2003 Tour Bootleg Style",
    "price": 24.00,
    "platform": "depop",
    "colors": ["black"],
    "style_tags": ["graphic tee", "vintage", "streetwear"],
}


def test_fit_card_empty_outfit_returns_error_string():
    # Failure mode: empty outfit → descriptive error string, never an exception.
    result = create_fit_card("", _SAMPLE_ITEM)
    assert isinstance(result, str)
    assert result.startswith("I couldn't create a fit card")


def test_fit_card_whitespace_outfit_returns_error_string():
    result = create_fit_card("   \n  ", _SAMPLE_ITEM)
    assert result.startswith("I couldn't create a fit card")


def test_fit_card_missing_item_details_returns_error_string():
    result = create_fit_card("Wear it with baggy jeans.", {"title": "Tee"})
    assert result.startswith("I couldn't create a fit card")


# ── LLM-backed tests (skipped automatically when no GROQ_API_KEY) ──────────────

import os

requires_groq = pytest.mark.skipif(
    not os.environ.get("GROQ_API_KEY"),
    reason="GROQ_API_KEY not set — skipping live LLM tests",
)


@requires_groq
def test_suggest_outfit_empty_wardrobe_still_returns_text():
    # Failure mode: empty wardrobe → general advice, non-empty string, no crash.
    result = suggest_outfit(_SAMPLE_ITEM, get_empty_wardrobe())
    assert isinstance(result, str)
    assert result.strip() != ""


@requires_groq
def test_suggest_outfit_with_wardrobe_returns_text():
    result = suggest_outfit(_SAMPLE_ITEM, get_example_wardrobe())
    assert isinstance(result, str)
    assert result.strip() != ""


@requires_groq
def test_fit_card_varies_across_runs():
    outfit = "Baggy dark-wash jeans and chunky white sneakers for an easy streetwear fit."
    runs = {create_fit_card(outfit, _SAMPLE_ITEM) for _ in range(3)}
    # With temperature=1.0 the captions should not all be identical.
    assert len(runs) > 1
