"""
PAT OS
internet/fetch.py

Safely retrieve readable text from webpages.

Web content is treated as untrusted information.
It can be read by PAT, but never directly execute
computer actions.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


REQUEST_TIMEOUT = 10
MAX_DOWNLOAD_BYTES = 1_500_000
MAX_TEXT_CHARS = 15_000
MAX_REDIRECTS = 3

USER_AGENT = (
    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 "
    "PAT-OS/0.5"
)


@dataclass
class PageContent:
    """Readable content retrieved from a webpage."""

    title: str
    url: str
    text: str


def _host_is_safe(hostname: str) -> bool:
    """
    Reject local/private network addresses.

    PAT's web reader should read public websites,
    not internal services on the computer/network.
    """

    hostname = hostname.strip().lower()

    if not hostname:
        return False

    if hostname in {
        "localhost",
        "localhost.localdomain",
    }:
        return False

    try:
        addresses = socket.getaddrinfo(
            hostname,
            None,
        )

    except socket.gaierror:
        return False

    for address in addresses:
        ip_text = address[4][0]

        try:
            ip = ipaddress.ip_address(
                ip_text
            )

        except ValueError:
            return False

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False

    return True


def _validate_url(
    url: str,
) -> tuple[bool, str]:
    """Validate a URL before PAT requests it."""

    try:
        parsed = urlparse(url)

    except ValueError:
        return False, "The URL was invalid."

    if parsed.scheme not in {
        "http",
        "https",
    }:
        return (
            False,
            "Only HTTP and HTTPS websites are supported.",
        )

    if not parsed.hostname:
        return (
            False,
            "The website address did not contain a hostname.",
        )

    if not _host_is_safe(
        parsed.hostname
    ):
        return (
            False,
            "PAT blocked that address for security reasons.",
        )

    return True, ""


def _download_page(
    url: str,
) -> tuple[bool, requests.Response | str]:
    """
    Download a webpage while validating redirects.
    """

    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "text/plain;q=0.9,*/*;q=0.5"
            ),
        }
    )

    current_url = url

    for _ in range(
        MAX_REDIRECTS + 1
    ):
        valid, error = _validate_url(
            current_url
        )

        if not valid:
            return False, error

        try:
            response = session.get(
                current_url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=False,
                stream=True,
            )

        except requests.RequestException as error:
            return (
                False,
                f"Website request failed: {error}",
            )

        if response.status_code in {
            301,
            302,
            303,
            307,
            308,
        }:
            redirect = response.headers.get(
                "Location"
            )

            response.close()

            if not redirect:
                return (
                    False,
                    "The website returned an invalid redirect.",
                )

            current_url = urljoin(
                current_url,
                redirect,
            )

            continue

        if response.status_code >= 400:
            status = response.status_code
            response.close()

            return (
                False,
                f"The website returned HTTP {status}.",
            )

        content_type = (
            response.headers
            .get("Content-Type", "")
            .lower()
        )

        if not (
            "text/html" in content_type
            or "application/xhtml+xml"
            in content_type
            or "text/plain" in content_type
        ):
            response.close()

            return (
                False,
                "That page is not readable webpage text.",
            )

        return True, response

    return (
        False,
        "The website redirected too many times.",
    )


def _read_limited_response(
    response: requests.Response,
) -> tuple[bool, bytes | str]:
    """Read a response without downloading huge files."""

    data = bytearray()

    try:
        for chunk in response.iter_content(
            chunk_size=8192
        ):
            if not chunk:
                continue

            data.extend(chunk)

            if len(data) > MAX_DOWNLOAD_BYTES:
                return (
                    False,
                    "The webpage was too large to read safely.",
                )

    finally:
        response.close()

    return True, bytes(data)


def _extract_text(
    html: str,
) -> tuple[str, str]:
    """Extract useful readable text from HTML."""

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    title = ""

    if soup.title:
        title = soup.title.get_text(
            " ",
            strip=True,
        )

    for element in soup(
        [
            "script",
            "style",
            "noscript",
            "svg",
            "canvas",
            "form",
            "nav",
            "footer",
        ]
    ):
        element.decompose()

    main_content = (
        soup.find("article")
        or soup.find("main")
        or soup.body
        or soup
    )

    text = main_content.get_text(
        "\n",
        strip=True,
    )

    cleaned_lines: list[str] = []

    for line in text.splitlines():
        cleaned = " ".join(
            line.split()
        )

        if not cleaned:
            continue

        cleaned_lines.append(
            cleaned
        )

    cleaned_text = "\n".join(
        cleaned_lines
    )

    return (
        title,
        cleaned_text[:MAX_TEXT_CHARS],
    )


def fetch_webpage(
    url: str,
) -> tuple[bool, PageContent | str]:
    """
    Retrieve readable text from a public webpage.
    """

    url = url.strip()

    if not url:
        return (
            False,
            "The website address was empty.",
        )

    valid, error = _validate_url(
        url
    )

    if not valid:
        return False, error

    success, result = _download_page(
        url
    )

    if not success:
        return False, str(result)

    if not isinstance(
        result,
        requests.Response,
    ):
        return (
            False,
            "The website response was invalid.",
        )

    final_url = result.url

    success, page_bytes = (
        _read_limited_response(
            result
        )
    )

    if not success:
        return False, str(page_bytes)

    if not isinstance(
        page_bytes,
        bytes,
    ):
        return (
            False,
            "The webpage data was invalid.",
        )

    encoding = (
        result.encoding
        or "utf-8"
    )

    try:
        html = page_bytes.decode(
            encoding,
            errors="replace",
        )

    except LookupError:
        html = page_bytes.decode(
            "utf-8",
            errors="replace",
        )

    title, text = _extract_text(
        html
    )

    if not text:
        return (
            False,
            "I could not extract readable text from that page.",
        )

    return (
        True,
        PageContent(
            title=title,
            url=final_url,
            text=text,
        ),
    )


if __name__ == "__main__":
    print("PAT Webpage Reader Test")
    print()

    test_url = input(
        "Website URL: "
    ).strip()

    success, result = fetch_webpage(
        test_url
    )

    if not success:
        print()
        print(result)

    elif isinstance(
        result,
        PageContent,
    ):
        print()
        print(
            f"Title: {result.title}"
        )

        print(
            f"URL: {result.url}"
        )

        print()
        print("--- PAGE TEXT ---")
        print()

        print(
            result.text[:5000]
        )