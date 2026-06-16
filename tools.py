"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.
    """
    listings = load_listings()

    # Filter by price
    if max_price is not None:
        listings = [item for item in listings if item["price"] <= max_price]

    # Filter by size (case-insensitive substring)
    if size is not None:
        size_lower = size.lower()
        listings = [
            item for item in listings
            if size_lower in item["size"].lower()
        ]

    # Score by keyword overlap with description
    keywords = [w.lower() for w in description.split() if len(w) > 1]

    def score(item):
        total = 0
        title_lower = item["title"].lower()
        desc_lower = item["description"].lower()
        tags = [t.lower() for t in item["style_tags"]]
        colors = [c.lower() for c in item["colors"]]
        brand = (item["brand"] or "").lower()

        for kw in keywords:
            if kw in title_lower:
                total += 2
            for tag in tags:
                if kw in tag:
                    total += 2
            if kw in desc_lower:
                total += 1
            for color in colors:
                if kw in color:
                    total += 1
            if kw in brand:
                total += 1
        return total

    scored = [(score(item), item) for item in listings]
    scored = [(s, item) for s, item in scored if s > 0]
    scored.sort(key=lambda x: x[0], reverse=True)

    return [item for _, item in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offers general styling advice for the item.
    """
    try:
        client = _get_groq_client()

        item_summary = (
            f"Item: {new_item['title']}\n"
            f"Category: {new_item['category']}\n"
            f"Style tags: {', '.join(new_item['style_tags'])}\n"
            f"Colors: {', '.join(new_item['colors'])}\n"
            f"Condition: {new_item['condition']}\n"
            f"Price: ${new_item['price']} on {new_item['platform']}"
        )

        wardrobe_items = wardrobe.get("items", [])

        if not wardrobe_items:
            prompt = (
                f"A user is considering buying this secondhand item:\n{item_summary}\n\n"
                "They don't have a wardrobe on file yet. Suggest 2 specific outfit ideas "
                "for this item — name the types of pieces that would pair well (e.g., "
                "'wide-leg trousers', 'chunky sneakers'), the overall vibe of each outfit, "
                "and one styling tip. Keep it practical and specific."
            )
        else:
            wardrobe_text = "\n".join(
                f"- {w['name']} ({w['category']}, colors: {', '.join(w['colors'])}, "
                f"tags: {', '.join(w['style_tags'])})"
                + (f" — {w['notes']}" if w.get("notes") else "")
                for w in wardrobe_items
            )
            prompt = (
                f"A user is considering buying this secondhand item:\n{item_summary}\n\n"
                f"Their current wardrobe:\n{wardrobe_text}\n\n"
                "Suggest 1–2 complete outfit combinations using the new item paired with "
                "specific named pieces from their wardrobe. For each outfit: name the exact "
                "wardrobe pieces used, describe the overall vibe, and include one styling tip. "
                "Be specific — reference actual item names from their wardrobe."
            )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=400,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"Could not generate outfit suggestion: {e}"


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, returns a descriptive error message string.
    """
    if not outfit or not outfit.strip():
        return "Could not create fit card — outfit description is empty."

    try:
        client = _get_groq_client()

        prompt = (
            f"Write a 2–4 sentence Instagram caption for this thrifted outfit.\n\n"
            f"Thrifted item: {new_item['title']} — ${new_item['price']} from {new_item['platform']}\n"
            f"Outfit: {outfit}\n\n"
            "Rules:\n"
            "- Write in first person, casual and authentic — like a real OOTD post\n"
            "- Mention the item name, price, and platform naturally (each once)\n"
            "- Capture the specific vibe of the outfit in concrete terms\n"
            "- No hashtags, no product-description tone\n"
            "- Sound like something worth sharing, not a listing"
        )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=1.2,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"Could not generate fit card: {e}"
