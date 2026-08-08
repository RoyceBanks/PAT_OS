"""
PAT OS
automation/file_manager.py

Safe local file-management tools for PAT.
"""

from __future__ import annotations

import os
from pathlib import Path


HOME_DIR = Path.home()

SAFE_LOCATIONS = {
    "desktop": HOME_DIR / "Desktop",
    "documents": HOME_DIR / "Documents",
    "downloads": HOME_DIR / "Downloads",
    "pictures": HOME_DIR / "Pictures",
    "videos": HOME_DIR / "Videos",
    "music": HOME_DIR / "Music",
}


def get_safe_location(
    location: str,
) -> Path | None:
    """Resolve an approved user folder."""

    cleaned = location.strip().lower()

    aliases = {
        "desktop": "desktop",
        "my desktop": "desktop",

        "documents": "documents",
        "document": "documents",
        "my documents": "documents",

        "downloads": "downloads",
        "download": "downloads",
        "my downloads": "downloads",

        "pictures": "pictures",
        "photos": "pictures",
        "my pictures": "pictures",

        "videos": "videos",
        "my videos": "videos",

        "music": "music",
        "my music": "music",
    }

    key = aliases.get(cleaned)

    if key is None:
        return None

    return SAFE_LOCATIONS.get(key)


def open_folder(
    location: str,
) -> tuple[bool, str]:
    """Open an approved user folder."""

    try:
        folder = get_safe_location(location)

        if folder is None:
            return (
                False,
                f"{location} is not an approved folder.",
            )

        if not folder.exists():
            return (
                False,
                f"I could not find your {location} folder.",
            )

        os.startfile(folder)

        return (
            True,
            f"Opening {location}.",
        )

    except Exception as error:
        return (
            False,
            f"I could not open {location}: {error}",
        )


def list_files(
    location: str,
    limit: int = 20,
) -> tuple[bool, str]:
    """List files in an approved user folder."""

    try:
        folder = get_safe_location(location)

        if folder is None:
            return (
                False,
                f"{location} is not an approved folder.",
            )

        if not folder.exists():
            return (
                False,
                f"I could not find your {location} folder.",
            )

        items = sorted(
            folder.iterdir(),
            key=lambda item: item.name.lower(),
        )

        if not items:
            return (
                True,
                f"Your {location} folder is empty.",
            )

        names = [
            item.name
            for item in items[:limit]
        ]

        response = (
            f"Files in {location}: "
            + ", ".join(names)
        )

        if len(items) > limit:
            response += (
                f". There are {len(items) - limit} "
                "more items."
            )

        return True, response

    except Exception as error:
        return (
            False,
            f"I could not list {location}: {error}",
        )


def create_folder(
    location: str,
    folder_name: str,
) -> tuple[bool, str]:
    """Create a new folder inside an approved location."""

    try:
        parent = get_safe_location(location)

        if parent is None:
            return (
                False,
                f"{location} is not an approved folder.",
            )

        folder_name = folder_name.strip()

        if not folder_name:
            return (
                False,
                "The folder name was empty.",
            )

        # Prevent paths such as ../../Windows
        if (
            "/" in folder_name
            or "\\" in folder_name
            or folder_name in {".", ".."}
        ):
            return (
                False,
                "That folder name is not allowed.",
            )

        new_folder = parent / folder_name

        if new_folder.exists():
            return (
                True,
                f"{folder_name} already exists in {location}.",
            )

        new_folder.mkdir()

        return (
            True,
            f"Created {folder_name} in {location}.",
        )

    except Exception as error:
        return (
            False,
            f"I could not create the folder: {error}",
        )


def find_file(
    filename: str,
) -> tuple[bool, str]:
    """
    Search approved user folders for a filename.
    """

    try:
        filename = filename.strip().lower()

        if not filename:
            return (
                False,
                "You did not give me a filename.",
            )

        matches = []

        for location_name, folder in SAFE_LOCATIONS.items():
            if not folder.exists():
                continue

            for path in folder.rglob("*"):
                try:
                    if (
                        path.is_file()
                        and filename in path.name.lower()
                    ):
                        matches.append(
                            (
                                location_name,
                                path,
                            )
                        )

                        if len(matches) >= 10:
                            break

                except OSError:
                    continue

            if len(matches) >= 10:
                break

        if not matches:
            return (
                False,
                f"I could not find {filename}.",
            )

        descriptions = []

        for location_name, path in matches:
            descriptions.append(
                f"{path.name} in {location_name}"
            )

        return (
            True,
            "I found: "
            + ", ".join(descriptions),
        )

    except Exception as error:
        return (
            False,
            f"I could not search for the file: {error}",
        )


if __name__ == "__main__":
    print("PAT File Manager Test")
    print()
    print("1. Open Downloads")
    print("2. List Downloads")
    print("3. Create test folder in Documents")
    print("4. Find a file")

    choice = input(
        "Select test: "
    ).strip()

    if choice == "1":
        print(
            open_folder("downloads")
        )

    elif choice == "2":
        print(
            list_files("downloads")
        )

    elif choice == "3":
        print(
            create_folder(
                "documents",
                "PAT_Test",
            )
        )

    elif choice == "4":
        filename = input(
            "Filename: "
        ).strip()

        print(
            find_file(filename)
        )

    else:
        print("Unknown test.")