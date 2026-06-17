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
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

# Model used for the two LLM-backed tools.
_MODEL = "llama-3.3-70b-versatile"


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _tokenize(text: str) -> list[str]:
    """Lowercase a string and split it into alphanumeric word tokens (len >= 2)."""
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) >= 2]


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

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()
    query_tokens = _tokenize(description or "")

    scored: list[tuple[int, dict]] = []
    for item in listings:
        # 1. Price filter (inclusive).
        if max_price is not None and item["price"] > max_price:
            continue

        # 2. Size filter — case-insensitive substring (e.g. "M" matches "S/M").
        if size is not None and size.strip():
            if size.strip().lower() not in str(item.get("size", "")).lower():
                continue

        # 3. Score by keyword overlap, weighting title and style_tags higher.
        title_blob = item.get("title", "").lower()
        tag_blob = " ".join(item.get("style_tags", [])).lower()
        other_blob = " ".join([
            item.get("description", ""),
            item.get("category", ""),
            " ".join(item.get("colors", [])),
            item.get("brand") or "",
            item.get("platform", ""),
        ]).lower()

        score = 0
        for token in query_tokens:
            if token in title_blob:
                score += 3
            if token in tag_blob:
                score += 3
            if token in other_blob:
                score += 1

        # 4. Drop anything with no keyword overlap.
        if score > 0:
            scored.append((score, item))

    # 5. Sort by score, highest first (stable — preserves dataset order on ties).
    scored.sort(key=lambda pair: pair[0], reverse=True)
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
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    item_desc = (
        f"- Title: {new_item.get('title')}\n"
        f"- Category: {new_item.get('category')}\n"
        f"- Colors: {', '.join(new_item.get('colors', []))}\n"
        f"- Style tags: {', '.join(new_item.get('style_tags', []))}\n"
        f"- Description: {new_item.get('description')}"
    )

    items = wardrobe.get("items", []) if wardrobe else []

    if not items:
        # Empty wardrobe → general styling advice, never crash or return "".
        prompt = (
            "A shopper is considering buying this secondhand item:\n\n"
            f"{item_desc}\n\n"
            "They haven't told you what's in their wardrobe yet. Suggest 1-2 "
            "complete outfit ideas for this piece using general styling advice: "
            "what categories, colors, and silhouettes pair well with it, and the "
            "overall vibe it suits. Keep it to a short, friendly paragraph or two."
        )
    else:
        wardrobe_lines = "\n".join(
            f"- {it.get('name')} ({it.get('category')}; "
            f"colors: {', '.join(it.get('colors', []))}; "
            f"tags: {', '.join(it.get('style_tags', []))})"
            for it in items
        )
        prompt = (
            "A shopper is considering buying this secondhand item:\n\n"
            f"{item_desc}\n\n"
            "Here is what they already own:\n"
            f"{wardrobe_lines}\n\n"
            "Suggest 1-2 complete outfits built around the new item. Name the "
            "specific wardrobe pieces (by their exact names) that you'd pair with "
            "it, briefly explain why they work together (colors, style tags), and "
            "describe the overall vibe. Keep it to a short, friendly paragraph or two."
        )

    client = _get_groq_client()
    response = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are FitFindr, a warm, knowledgeable thrift stylist.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    return (response.choices[0].message.content or "").strip()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    _INCOMPLETE = (
        "I couldn't create a fit card because the outfit suggestion or "
        "listing details were incomplete."
    )

    # 1. Guard against an empty/whitespace outfit or missing listing details.
    if not outfit or not outfit.strip():
        return _INCOMPLETE
    if not new_item or not all(
        new_item.get(k) for k in ("title", "price", "platform")
    ):
        return _INCOMPLETE

    # 2. Build the prompt with item details + the outfit.
    prompt = (
        "Write a short, shareable OOTD caption (2-4 sentences) for a thrifted find.\n\n"
        f"Item: {new_item['title']}\n"
        f"Price: ${new_item['price']}\n"
        f"Platform: {new_item['platform']}\n"
        f"Colors: {', '.join(new_item.get('colors', []))}\n"
        f"Style tags: {', '.join(new_item.get('style_tags', []))}\n\n"
        f"Outfit it's being styled in:\n{outfit}\n\n"
        "Rules:\n"
        "- Sound like a real person's OOTD post, not a product description.\n"
        "- Mention the item name, price, and platform naturally — once each.\n"
        "- Capture the outfit vibe in specific terms.\n"
        "- Just return the caption text, no quotes or hashtag dump."
    )

    # 3. Call the LLM with a higher temperature so captions vary run to run.
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are FitFindr, writing punchy, authentic thrift OOTD captions.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=1.0,
    )
    caption = (response.choices[0].message.content or "").strip()
    return caption if caption else _INCOMPLETE
