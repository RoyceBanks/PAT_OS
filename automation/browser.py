"""
PAT OS v0.6.0
automation/browser.py

Browser and web-search automation.
"""

from __future__ import annotations

import re
import webbrowser
import time
import pyautogui
import pyperclip
from config import SEARCH_ENGINE_URL
from brain.session_context import (
    remember_research_sources,
)
from internet.search import search_internet
from urllib.parse import (
    urlencode,
    urlparse,
)

from automation.window_controls import (
    focus_window,
)

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


def _get_url_hostname(
    url: str,
) -> str:
    """Return a normalized hostname from a URL."""

    try:
        hostname = (
            urlparse(url).hostname
            or ""
        ).strip().lower()

        if hostname.startswith("www."):
            hostname = hostname[4:]

        return hostname

    except Exception:
        return ""


# ==========================================================
# OPEN WEBSITE
# ==========================================================

def open_website(
    website_name: str,
) -> tuple[bool, str]:
    """
    Open a known website.

    When Firefox is already running, create a new foreground
    tab so later contextual browser actions can safely verify it.
    """

    normalized_name = normalize_website_name(
        website_name
    )

    url = WEBSITES.get(
        normalized_name
    )

    if url is None:
        return (
            False,
            (
                f"I do not have {website_name} "
                "configured as a website."
            ),
        )

    try:
        # If Firefox already exists, explicitly create a
        # foreground tab instead of relying on webbrowser's
        # new-tab behavior.
        firefox_ready, _message = focus_window(
            "firefox"
        )

        if firefox_ready:
            pyautogui.hotkey(
                "ctrl",
                "t",
            )

            time.sleep(0.15)

            pyautogui.write(
                url,
                interval=0.01,
            )

            pyautogui.press(
                "enter"
            )

            return (
                True,
                f"Opening {normalized_name}.",
            )

        # Firefox is not currently open.
        # Let Windows/default-browser handling start it.
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

        # Give Firefox a moment to create its first window,
        # then bring that window forward.
        time.sleep(0.75)

        focus_window(
            "firefox"
        )

        return (
            True,
            f"Opening {normalized_name}.",
        )

    except Exception as error:
        return (
            False,
            (
                f"I could not open "
                f"{normalized_name}: {error}"
            ),
        )

def close_website_tab(
    website_name: str,
) -> tuple[bool, str]:
    """
    Safely close the active Firefox tab only when PAT
    can verify that the tab belongs to the requested website.
    """

    normalized_name = normalize_website_name(
        website_name
    )

    expected_url = WEBSITES.get(
        normalized_name
    )

    if expected_url is None:
        return (
            False,
            (
                f"I do not have {website_name} "
                "configured as a website."
            ),
        )

    expected_host = _get_url_hostname(
        expected_url
    )

    success, _message = focus_window(
        "firefox"
    )

    if not success:
        return (
            False,
            (
                "I could not find Firefox, "
                f"so I did not close {normalized_name}."
            ),
        )

    previous_clipboard = None

    try:
        try:
            previous_clipboard = (
                pyperclip.paste()
            )
        except Exception:
            previous_clipboard = None

        # Read the URL from Firefox's active tab.
        pyautogui.hotkey(
            "ctrl",
            "l",
        )

        time.sleep(0.15)

        pyautogui.hotkey(
            "ctrl",
            "c",
        )

        time.sleep(0.15)

        current_url = (
            pyperclip.paste()
            .strip()
        )

        # Leave the address bar without navigating.
        pyautogui.press(
            "esc"
        )

    except Exception as error:
        return (
            False,
            (
                "I could not verify the active "
                f"Firefox tab: {error}"
            ),
        )

    finally:
        if previous_clipboard is not None:
            try:
                pyperclip.copy(
                    previous_clipboard
                )
            except Exception:
                pass

    current_host = _get_url_hostname(
        current_url
    )

    if (
        not current_host
        or current_host != expected_host
    ):
        return (
            False,
            (
                "I won't close the current Firefox tab "
                f"because I could not verify that it "
                f"is {normalized_name}."
            ),
        )

    try:
        pyautogui.hotkey(
            "ctrl",
            "w",
        )

        return (
            True,
            f"Closed the {normalized_name} tab.",
        )

    except Exception as error:
        return (
            False,
            (
                f"I could not close the "
                f"{normalized_name} tab: {error}"
            ),
        )
# ==========================================================
# WEB SEARCH
# ==========================================================

def search_web(
    query: str,
) -> tuple[bool, str]:
    """Search the web and remember openable results."""

    cleaned_query = query.strip(
        " \t\r\n.,!?"
    )

    if not cleaned_query:
        return (
            False,
            "I need something to search for.",
        )

    success, result = search_internet(
        cleaned_query
    )

    if not success:
        return (
            False,
            str(result),
        )

    if not isinstance(result, list):
        return (
            False,
            "I could not read the search results.",
        )

    sources: list[tuple[str, str]] = []

    for item in result:
        title = item.title.strip()
        url = item.url.strip()

        if not url:
            continue

        if not title:
            title = url

        sources.append(
            (
                title,
                url,
            )
        )

    if not sources:
        return (
            False,
            "I found results, but none had an openable link.",
        )

    remember_research_sources(
        sources
    )

    descriptions = []

    for number, (
        title,
        _,
    ) in enumerate(
        sources,
        start=1,
    ):
        descriptions.append(
            f"{number}. {title}"
        )

    return (
        True,
        (
            f"I found {len(sources)} results. "
            + " ".join(descriptions)
        ),
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
    