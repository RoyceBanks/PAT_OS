"""
PAT OS v0.6.0
automation/browser.py

Browser and web-search automation.
"""

from __future__ import annotations

import re
import webbrowser
from urllib.parse import urlencode

from config import SEARCH_ENGINE_URL


# ==========================================================
# KNOWN WEBSITES
# ==========================================================

WEBSITES: dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "reddit": "https://www.reddit.com",
    "wikipedia": "https://www.wikipedia.org",
    "spotify": "https://open.spotify.com",
    "amazon": "https://www.amazon.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "tiktok": "https://www.tiktok.com",
}


WEBSITE_ALIASES: dict[str, str] = {
    "you tube": "youtube",
    "git hub": "github",
    "google mail": "gmail",
    "email": "gmail",
    "wiki": "wikipedia",
}


# ==========================================================
# HELPERS
# ==========================================================

def normalize_website_name(
    website_name: str,
) -> str:
    """Clean a spoken website name."""

    cleaned_name = website_name.strip().lower()

    cleaned_name = re.sub(
        r"^[\s.,!?;:'\"]+|[\s.,!?;:'\"]+$",
        "",
        cleaned_name,
    )

    cleaned_name = " ".join(
        cleaned_name.split()
    )

    return WEBSITE_ALIASES.get(
        cleaned_name,
        cleaned_name,
    )


def is_known_website(
    website_name: str,
) -> bool:
    """Check whether PAT knows a website."""

    normalized_name = normalize_website_name(
        website_name
    )

    return normalized_name in WEBSITES


# ==========================================================
# OPEN WEBSITE
# ==========================================================

def open_website(
    website_name: str,
) -> tuple[bool, str]:
    """Open a known website."""

    normalized_name = normalize_website_name(
        website_name
    )

    url = WEBSITES.get(normalized_name)

    if url is None:
        return (
            False,
            f"I do not have {website_name} "
            f"configured as a website.",
        )

    try:
        opened = webbrowser.open(
            url,
            new=2,
            autoraise=True,
        )

        if not opened:
            return (
                False,
                f"I could not open {normalized_name}.",
            )

        return (
            True,
            f"Opening {normalized_name}.",
        )

    except Exception as error:
        return (
            False,
            f"I could not open "
            f"{normalized_name}: {error}",
        )


# ==========================================================
# WEB SEARCH
# ==========================================================

def search_web(
    query: str,
) -> tuple[bool, str]:
    """Search the internet."""

    cleaned_query = query.strip(
        " \t\r\n.,!?"
    )

    if not cleaned_query:
        return (
            False,
            "I need something to search for.",
        )

    parameters = urlencode(
        {
            "q": cleaned_query,
        }
    )

    url = (
        f"{SEARCH_ENGINE_URL}?"
        f"{parameters}"
    )

    try:
        opened = webbrowser.open(
            url,
            new=2,
            autoraise=True,
        )

        if not opened:
            return (
                False,
                "I could not open the web search.",
            )

        return (
            True,
            f"Searching the web for "
            f"{cleaned_query}.",
        )

    except Exception as error:
        return (
            False,
            f"I could not perform "
            f"that search: {error}",
        )


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":
    print("PAT Browser Test")
    print()
    print("1 - Open website")
    print("2 - Search web")
    print()

    selection = input(
        "Choose a test: "
    ).strip()

    if selection == "1":
        website = input(
            "Website: "
        )

        success, message = open_website(
            website
        )

    elif selection == "2":
        query = input(
            "Search for: "
        )

        success, message = search_web(
            query
        )

    else:
        success = False
        message = "Invalid selection."

    print()
    print(message)
    print(f"Success: {success}")
    