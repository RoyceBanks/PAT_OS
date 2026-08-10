"""
PAT OS
automation/file_manager.py

Safe local file-management tools for PAT.
"""


from __future__ import annotations
import os
import shutil
from send2trash import send2trash
import re

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

IGNORED_SEARCH_DIRECTORIES = {
    ".git",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def _is_ignored_search_path(
    path: Path,
    root: Path,
) -> bool:
    """Return True when a file is inside a development/cache folder."""

    try:
        directory_parts = (
            path.relative_to(root).parts[:-1]
        )
    except ValueError:
        return True

    for part in directory_parts:
        lowered = part.casefold()

        if lowered.startswith(".venv"):
            return True

        if lowered in IGNORED_SEARCH_DIRECTORIES:
            return True

    return False

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

def _normalize_filename_search(
    value: str,
) -> str:
    """
    Normalize filenames for voice-friendly searching.

    Examples:
        PAT_delete_test.txt
        pat delete test
        PAT-delete-test

    all become similar searchable text.
    """

    value = value.casefold()

    # Treat common filename separators as spaces.
    value = re.sub(
        r"[._\-]+",
        " ",
        value,
    )

    # Remove other punctuation.
    value = re.sub(
        r"[^a-z0-9\s]",
        " ",
        value,
    )

    return " ".join(
        value.split()
    )

def find_file(
    
    filename: str,
    limit: int = 10,
) -> tuple[bool, str]:
    """Search PAT's approved folders for a file."""

    try:
        filename = filename.strip()

        if not filename:
            return (
                False,
                "You did not give me a filename to search for.",
            )

        search_text = _normalize_filename_search(
            filename
        )

        if not search_text:
            return (
                False,
                "That filename was not valid.",
            )

        search_words = search_text.split()

        matches = []

        clear_file_results()

        for location_name, root in SAFE_LOCATIONS.items():
            if not root.exists():
                continue

            try:
                for path in root.rglob("*"):
                    try:
                        if not path.is_file():
                            continue

                        if _is_ignored_search_path(
                            path,
                            root,
                        ):
                            continue

                        candidate = _normalize_filename_search(
                            path.name
                        )

                        candidate_words = candidate.split()

                        # Every word spoken by the user must
                        # appear somewhere in the filename.
                        if not all(
                            word in candidate_words
                            for word in search_words
                        ):
                            continue

                        matches.append(
                            (
                                location_name,
                                path,
                            )
                        )

                        if len(matches) >= limit:
                            break

                    except OSError:
                        continue

            except OSError:
                continue

            if len(matches) >= limit:
                break

        if not matches:
            return (
                False,
                f"I could not find {filename}.",
            )

        remember_file_results(
            [
                str(path)
                for _, path in matches
            ]
        )

        descriptions = []

        for number, (
            location_name,
            path,
        ) in enumerate(
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
            (
                f"I found {len(matches)} {file_word}. "
                + " ".join(descriptions)
            ),
        )

    except Exception as error:
        return (
            False,
            f"I could not search for that file: {error}",
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

def _get_found_file(
    number: int,
) -> tuple[Path | None, str | None]:
    """Resolve a numbered previous file-search result."""

    results = get_file_results()

    index = number - 1

    if index < 0 or index >= len(results):
        return None, "I do not have that many file results."

    path = Path(results[index])

    if not path.exists():
        return None, "That file no longer exists."

    if not path.is_file():
        return None, "That result is not a file."

    if not _is_safe_path(path):
        return None, "That file is outside PAT's approved locations."

    return path, None

def rename_found_file(
    number: int,
    new_name: str,
) -> tuple[bool, str]:
    """Rename a file from PAT's latest file-search results."""

    try:
        path, error = _get_found_file(number)

        if path is None:
            return False, error or "I could not find that file."

        new_name = new_name.strip()

        if not new_name:
            return False, "The new filename was empty."

        if (
            "/" in new_name
            or "\\" in new_name
            or new_name in {".", ".."}
        ):
            return False, "That filename is not allowed."

        target = path.parent / new_name

        if target.exists():
            return (
                False,
                f"A file named {new_name} already exists there.",
            )

        if not _is_safe_path(target):
            return (
                False,
                "The new file location is not approved.",
            )

        path.rename(target)

        results = get_file_results()
        results[number - 1] = str(target)
        remember_file_results(results)

        return (
            True,
            f"Renamed {path.name} to {target.name}.",
        )

    except Exception as error:
        return (
            False,
            f"I could not rename that file: {error}",
        )

def move_found_file(
    number: int,
    destination: str,
) -> tuple[bool, str]:
    """Move a previous file-search result to an approved folder."""

    try:
        path, error = _get_found_file(number)

        if path is None:
            return False, error or "I could not find that file."

        destination_folder = get_safe_location(
            destination
        )

        if destination_folder is None:
            return (
                False,
                f"{destination} is not an approved folder.",
            )

        if not destination_folder.exists():
            return (
                False,
                f"I could not find your {destination} folder.",
            )

        target = destination_folder / path.name

        if target.exists():
            return (
                False,
                f"{path.name} already exists in {destination}.",
            )

        if not _is_safe_path(target):
            return (
                False,
                "That destination is outside PAT's approved locations.",
            )

        shutil.move(
            str(path),
            str(target),
        )

        results = get_file_results()
        results[number - 1] = str(target)
        remember_file_results(results)

        return (
            True,
            f"Moved {path.name} to {destination}.",
        )

    except Exception as error:
        return (
            False,
            f"I could not move that file: {error}",
        )

def copy_found_file(
    number: int,
    destination: str,
) -> tuple[bool, str]:
    """Copy a previous file-search result to an approved folder."""

    try:
        path, error = _get_found_file(number)

        if path is None:
            return (
                False,
                error or "I could not find that file.",
            )

        destination_folder = get_safe_location(
            destination
        )

        if destination_folder is None:
            return (
                False,
                f"{destination} is not an approved folder.",
            )

        if not destination_folder.exists():
            return (
                False,
                f"I could not find your {destination} folder.",
            )

        target = destination_folder / path.name

        if target.exists():
            return (
                False,
                f"{path.name} already exists in {destination}.",
            )

        if not _is_safe_path(target):
            return (
                False,
                "That destination is outside PAT's approved locations.",
            )

        shutil.copy2(
            str(path),
            str(target),
        )

        # Make the new copy the active version of this
        # conversational file result.
        results = get_file_results()
        results[number - 1] = str(target)
        remember_file_results(results)

        return (
            True,
            f"Copied {path.name} to {destination}.",
        )

    except Exception as error:
        return (
            False,
            f"I could not copy that file: {error}",
        )

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

def prepare_found_file_delete(
    number: int,
) -> tuple[bool, str, str | None]:
    """
    Prepare a previous file-search result for deletion.

    Nothing is deleted here. The exact path is returned so
    PAT can request confirmation first.
    """

    try:
        path, error = _get_found_file(number)

        if path is None:
            return (
                False,
                error or "I could not find that file.",
                None,
            )

        return (
            True,
            (
                f"Are you sure you want me to move "
                f"{path.name} to the Recycle Bin?"
            ),
            str(path),
        )

    except Exception as error:
        return (
            False,
            f"I could not prepare that file for deletion: {error}",
            None,
        )


def delete_file_path(
    path_value: str,
) -> tuple[bool, str]:
    """
    Move an explicitly confirmed file to the Recycle Bin.
    """

    try:
        path = Path(path_value)

        if not path.exists():
            return (
                False,
                "That file no longer exists.",
            )

        if not path.is_file():
            return (
                False,
                "That item is not a file.",
            )

        if not _is_safe_path(path):
            return (
                False,
                "That file is outside PAT's approved locations.",
            )

        filename = path.name

        send2trash(
            str(path)
        )

        # Remove the deleted file from previous search results.
        results = [
            result
            for result in get_file_results()
            if Path(result) != path
        ]

        remember_file_results(
            results
        )

        return (
            True,
            f"Moved {filename} to the Recycle Bin.",
        )

    except Exception as error:
        return (
            False,
            f"I could not delete that file: {error}",
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