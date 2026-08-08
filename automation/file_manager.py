"""
PAT OS
automation/file_manager.py

Safe local file-management tools for PAT.
"""

from __future__ import annotations

import os
from pathlib import Path
from brain.session_context import (
    clear_file_results,
    get_file_results,
    remember_file_results,
)



HOME_DIR = Path.home()


def _get_onedrive_dir() -> Path | None:
    """Return the user's OneDrive directory when available."""

    value = os.environ.get("OneDrive")

    if not value:
        return None

    path = Path(value)

    if path.exists():
        return path

    return None


ONEDRIVE_DIR = _get_onedrive_dir()


def _user_folder(
    name: str,
) -> Path:
    """
    Resolve a common Windows user folder.

    Prefer the OneDrive version when it exists,
    otherwise fall back to the normal user folder.
    """

    if ONEDRIVE_DIR is not None:
        onedrive_folder = (
            ONEDRIVE_DIR
            / name
        )

        if onedrive_folder.exists():
            return onedrive_folder

    return HOME_DIR / name


SAFE_LOCATIONS = {
    "desktop": _user_folder("Desktop"),
    "documents": _user_folder("Documents"),
    "downloads": _user_folder("Downloads"),
    "pictures": _user_folder("Pictures"),
    "videos": _user_folder("Videos"),
    "music": _user_folder("Music"),
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
        clear_file_results()

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

        remember_file_results(
            [
                str(path)
                for _, path in matches
            ]
        )


        if not matches:
            return (
                False,
                f"I could not find {filename}.",
            )

        descriptions = []

        for number, (location_name, path) in enumerate(
            matches,
            start=1,
        ):
            root = SAFE_LOCATIONS.get(
                location_name
            )

            try:
                if root is not None:
                    display_path = path.relative_to(
                        root
                    )
                else:
                    display_path = path.name

            except ValueError:
                display_path = path.name

            descriptions.append(
                f"{number}. {display_path}"
            )


        file_word = (
            "file"
            if len(matches) == 1
            else "files"
        )

        return (
            True,
            f"I found {len(matches)} {file_word}. "
            + " ".join(descriptions),
        )

    except Exception as error:
        return (
            False,
            f"I could not search for the file: {error}",
        )

def _is_safe_path(
    path: Path,
) -> bool:
    """Verify that a path is inside an approved PAT location."""

    try:
        resolved = path.resolve()

        for folder in SAFE_LOCATIONS.values():
            if not folder.exists():
                continue

            safe_root = folder.resolve()

            if resolved.is_relative_to(safe_root):
                return True

        return False

    except Exception:
        return False


def open_found_file(
    number: int,
) -> tuple[bool, str]:
    """Open a file from PAT's latest file search."""

    try:
        results = get_file_results()

        index = number - 1

        if index < 0 or index >= len(results):
            return (
                False,
                "I do not have that many file results.",
            )

        path = Path(results[index])

        if not path.exists():
            return (
                False,
                "That file no longer exists.",
            )

        if not path.is_file():
            return (
                False,
                "That result is not a file.",
            )

        if not _is_safe_path(path):
            return (
                False,
                "That file is outside PAT's approved locations.",
            )

        os.startfile(path)

        return (
            True,
            f"Opening {path.name}.",
        )

    except Exception as error:
        return (
            False,
            f"I could not open that file: {error}",
        )


def open_found_file_folder(
    number: int,
) -> tuple[bool, str]:
    """Open the folder containing a previous file result."""

    try:
        results = get_file_results()

        index = number - 1

        if index < 0 or index >= len(results):
            return (
                False,
                "I do not have that many file results.",
            )

        path = Path(results[index])

        if not path.exists():
            return (
                False,
                "That file no longer exists.",
            )

        if not _is_safe_path(path):
            return (
                False,
                "That file is outside PAT's approved locations.",
            )

        os.startfile(path.parent)

        return (
            True,
            f"Opening the folder containing {path.name}.",
        )

    except Exception as error:
        return (
            False,
            f"I could not open that folder: {error}",
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