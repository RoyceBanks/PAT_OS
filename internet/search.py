"""
PAT OS
internet/search.py

Live internet search for PAT.

Web content is treated as untrusted information.
It is never allowed to execute computer actions.
"""

from __future__ import annotations

from dataclasses import dataclass

from ddgs import DDGS


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


def search_internet(
    query: str,
    max_results: int = 5,
) -> tuple[bool, list[SearchResult] | str]:
    """
    Search the internet and return structured results.
    """

    query = query.strip()

    if not query:
        return False, "The search query was empty."

    try:
        results: list[SearchResult] = []

        with DDGS() as ddgs:
            raw_results = ddgs.text(
                query,
                max_results=max_results,
            )

            for item in raw_results:
                title = str(
                    item.get("title", "")
                ).strip()

                url = str(
                    item.get("href", "")
                ).strip()

                snippet = str(
                    item.get("body", "")
                ).strip()

                if not title and not snippet:
                    continue

                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                    )
                )

        if not results:
            return (
                False,
                "I could not find any search results.",
            )

        return True, results

    except Exception as error:
        return (
            False,
            f"Internet search failed: {error}",
        )


def format_search_results(
    results: list[SearchResult],
) -> str:
    """Format results for testing and AI processing."""

    lines: list[str] = []

    for number, result in enumerate(
        results,
        start=1,
    ):
        lines.append(
            f"{number}. {result.title}"
        )

        if result.snippet:
            lines.append(
                f"   {result.snippet}"
            )

        if result.url:
            lines.append(
                f"   Source: {result.url}"
            )

        lines.append("")

    return "\n".join(lines).strip()


if __name__ == "__main__":
    print("PAT Internet Search Test")
    print()

    query = input(
        "Search for: "
    ).strip()

    success, result = search_internet(
        query
    )

    if not success:
        print(result)

    else:
        print()
        print(
            format_search_results(result)
        )