"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """Initialize and return a fresh session dict for one user interaction."""
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "selected_item": None,
        "wardrobe": wardrobe,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
    }


# ── query parsing ─────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query.
    Uses regex — deterministic, no LLM call needed.
    """
    # Extract price: "under $30", "below 40", "max $25", "< $50"
    price_match = re.search(
        r'(?:under|below|max|<)\s*\$?(\d+(?:\.\d+)?)',
        query,
        re.IGNORECASE,
    )
    max_price = float(price_match.group(1)) if price_match else None

    # Extract size: common size labels
    size_match = re.search(
        r'\b(XXS|XS|S/M|M/L|XL|XXL|W\d+(?:\s*L\d+)?|US\s*\d+(?:\.\d+)?|[SMLX]{1,3})\b',
        query,
        re.IGNORECASE,
    )
    size = size_match.group(1) if size_match else None

    # Build description: remove price and size fragments from the query
    desc = query
    if price_match:
        desc = desc[:price_match.start()] + desc[price_match.end():]
    if size_match:
        # Also remove the word "size" before the match if present
        desc = re.sub(r'\b(?:size\s+)?' + re.escape(size_match.group(1)) + r'\b', '', desc, flags=re.IGNORECASE)

    # Clean up leftover punctuation and whitespace
    desc = re.sub(r'[,\.]+', ' ', desc)
    desc = re.sub(r'\s{2,}', ' ', desc).strip()

    # Remove trailing filler phrases that don't help search
    desc = re.sub(
        r'\b(?:i(?:\'m)?\s+(?:looking\s+for|want|need)|find\s+me|show\s+me)\b',
        '',
        desc,
        flags=re.IGNORECASE,
    ).strip()

    return {
        "description": desc or query,
        "size": size,
        "max_price": max_price,
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Returns:
        The session dict. Check session["error"] first — if not None, the
        interaction ended early and outfit_suggestion / fit_card will be None.
    """
    # Step 1: Initialize session
    session = _new_session(query, wardrobe)

    # Step 2: Parse query
    parsed = _parse_query(query)
    session["parsed"] = parsed

    # Step 3: Search listings
    results = search_listings(
        parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    session["search_results"] = results

    # Branch: early exit if nothing found
    if not results:
        parts = [f"No listings found for '{parsed['description']}'"]
        if parsed["size"]:
            parts.append(f"in size {parsed['size']}")
        if parsed["max_price"]:
            parts.append(f"under ${parsed['max_price']:.0f}")
        session["error"] = (
            " ".join(parts)
            + ". Try broader terms or remove the size/price filters."
        )
        return session

    # Step 4: Select top result
    session["selected_item"] = results[0]

    # Step 5: Suggest outfit
    session["outfit_suggestion"] = suggest_outfit(
        session["selected_item"],
        session["wardrobe"],
    )

    # Step 6: Create fit card
    session["fit_card"] = create_fit_card(
        session["outfit_suggestion"],
        session["selected_item"],
    )

    # Step 7: Return completed session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
