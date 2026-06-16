"""
tests/test_tools.py

Unit tests for the three FitFindr tools.
Run with: pytest tests/

Each failure mode has its own test so regressions are easy to spot.
"""

import pytest
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=30)
    assert all(item["price"] <= 30 for item in results)


def test_search_size_filter():
    results = search_listings("top", size="M", max_price=None)
    assert len(results) > 0
    # Every returned item's size field should contain "m" (case-insensitive)
    for item in results:
        assert "m" in item["size"].lower()


def test_search_no_price_filter_returns_more():
    with_cap = search_listings("vintage", size=None, max_price=20)
    without_cap = search_listings("vintage", size=None, max_price=None)
    assert len(without_cap) >= len(with_cap)


def test_search_returns_sorted_by_relevance():
    results = search_listings("vintage graphic tee", size=None, max_price=None)
    assert len(results) > 1
    # First result should mention "graphic" or "tee" in title or tags
    top = results[0]
    title_tags = top["title"].lower() + " " + " ".join(top["style_tags"]).lower()
    assert any(kw in title_tags for kw in ["graphic", "tee", "vintage"])


# ── suggest_outfit ────────────────────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results, "Need at least one result to test suggest_outfit"
    output = suggest_outfit(results[0], get_example_wardrobe())
    assert isinstance(output, str)
    assert len(output) > 10


def test_suggest_outfit_empty_wardrobe():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results, "Need at least one result to test suggest_outfit"
    output = suggest_outfit(results[0], get_empty_wardrobe())
    # Must return a non-empty string, not raise an exception
    assert isinstance(output, str)
    assert len(output) > 10


# ── create_fit_card ───────────────────────────────────────────────────────────

def test_create_fit_card_empty_outfit():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results
    output = create_fit_card("", results[0])
    # Must return an error string, not raise an exception
    assert isinstance(output, str)
    assert len(output) > 0
    assert "empty" in output.lower() or "could not" in output.lower()


def test_create_fit_card_whitespace_outfit():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results
    output = create_fit_card("   ", results[0])
    assert isinstance(output, str)
    assert "empty" in output.lower() or "could not" in output.lower()


def test_create_fit_card_returns_string():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results
    outfit = "Pair with baggy jeans and white tank for a streetwear look."
    output = create_fit_card(outfit, results[0])
    assert isinstance(output, str)
    assert len(output) > 10
