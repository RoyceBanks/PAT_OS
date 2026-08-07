"""
PAT OS v0.3
setup_pat.py

PAT OS setup and installation manager.

Stage 1:
- Check Python
- Check project folders
- Check required project files
- Check virtual environment
- Check Ollama
- Check PAT Ollama model
- Check Piper voice
- Check memory database
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path


# ==========================================================
# PROJECT PATHS
# ==========================================================

ROOT_DIR = Path(__file__).resolve().parent

DATA_DIR = ROOT_DIR / "data"
MODEL_DIR = ROOT_DIR / "models"
VOICE_DIR = MODEL_DIR / "voices"
LOG_DIR = ROOT_DIR / "logs"

VOICE_NAME = "en_US-lessac-medium"

VOICE_MODEL = VOICE_DIR / f"{VOICE_NAME}.onnx"
VOICE_CONFIG = VOICE_DIR / f"{VOICE_NAME}.onnx.json"

MEMORY_DATABASE = DATA_DIR / "memory.db"


# ==========================================================
# DISPLAY HELPERS
# ==========================================================

def print_header(title: str) -> None:
    """Print a setup section header."""

    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def success(message: str) -> None:
    """Display a successful setup check."""

    print(f"[OK]   {message}")


def warning(message: str) -> None:
    """Display a warning."""

    print(f"[WARN] {message}")


def failure(message: str) -> None:
    """Display a failed setup check."""

    print(f"[FAIL] {message}")


# ==========================================================
# PYTHON
# ==========================================================

def check_python() -> bool:
    """Verify Python is new enough for PAT."""

    print_header("Python")

    version = sys.version_info

    version_text = (
        f"{version.major}."
        f"{version.minor}."
        f"{version.micro}"
    )

    print(f"Python version: {version_text}")

    if version < (3, 11):
        failure(
            "PAT requires Python 3.11 or newer."
        )
        return False

    success("Python version is supported.")

    return True


# ==========================================================
# VIRTUAL ENVIRONMENT
# ==========================================================

def check_virtual_environment() -> bool:
    """Check whether PAT is running inside a virtual environment."""

    print_header("Virtual Environment")

    inside_venv = (
        hasattr(sys, "real_prefix")
        or sys.base_prefix != sys.prefix
    )

    if inside_venv:
        success(
            f"Virtual environment active: {sys.prefix}"
        )
        return True

    warning(
        "PAT is not currently running inside a virtual environment."
    )

    return False


# ==========================================================
# PROJECT DIRECTORIES
# ==========================================================

def check_directories() -> bool:
    """Create required PAT directories if they are missing."""

    print_header("Project Directories")

    directories = [
        DATA_DIR,
        MODEL_DIR,
        VOICE_DIR,
        LOG_DIR,
    ]

    all_good = True

    for directory in directories:
        try:
            directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            success(
                f"Directory ready: "
                f"{directory.relative_to(ROOT_DIR)}"
            )

        except Exception as error:
            failure(
                f"Could not create {directory}: {error}"
            )

            all_good = False

    return all_good


# ==========================================================
# REQUIRED PROJECT FILES
# ==========================================================

def check_project_files() -> bool:
    """Check for important PAT source files."""

    print_header("PAT Project Files")

    required_files = [
        ROOT_DIR / "main.py",
        ROOT_DIR / "config.py",
        ROOT_DIR / "core" / "router.py",
        ROOT_DIR / "core" / "planner.py",
        ROOT_DIR / "brain" / "ai.py",
        ROOT_DIR / "brain" / "memory.py",
        ROOT_DIR / "automation" / "apps.py",
        ROOT_DIR / "engines" / "task_engine.py",
        ROOT_DIR / "speech" / "listen.py",
        ROOT_DIR / "voice" / "speak.py",
        ROOT_DIR / "wakeword" / "detector.py",
        ROOT_DIR / "Modelfile",
    ]

    all_good = True

    for file_path in required_files:
        relative_path = file_path.relative_to(
            ROOT_DIR
        )

        if file_path.exists():
            success(str(relative_path))

        else:
            failure(
                f"Missing: {relative_path}"
            )

            all_good = False

    return all_good


# ==========================================================
# OLLAMA
# ==========================================================

def find_ollama() -> str | None:
    """Find the Ollama executable."""

    return shutil.which("ollama")


def check_ollama() -> bool:
    """Verify Ollama is installed."""

    print_header("Ollama")

    ollama_path = find_ollama()

    if ollama_path is None:
        failure(
            "Ollama was not found."
        )

        return False

    success(
        f"Ollama found: {ollama_path}"
    )

    try:
        result = subprocess.run(
            [
                ollama_path,
                "--version",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        output = (
            result.stdout.strip()
            or result.stderr.strip()
        )

        if output:
            print(f"       {output}")

        return result.returncode == 0

    except Exception as error:
        failure(
            f"Could not run Ollama: {error}"
        )

        return False


# ==========================================================
# PAT AI MODEL
# ==========================================================

def check_pat_model() -> bool:
    """Check whether the custom PAT Ollama model exists."""

    print_header("PAT AI Model")

    ollama_path = find_ollama()

    if ollama_path is None:
        failure(
            "Cannot check PAT model because Ollama "
            "is not installed."
        )

        return False

    try:
        result = subprocess.run(
            [
                ollama_path,
                "list",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )

        output = result.stdout.lower()

        if "pat:" in output or "pat " in output:
            success(
                "PAT Ollama model is installed."
            )

            return True

        warning(
            "PAT Ollama model was not found."
        )

        return False

    except Exception as error:
        failure(
            f"Could not check Ollama models: {error}"
        )

        return False


# ==========================================================
# PIPER VOICE
# ==========================================================

def download_voice_model() -> bool:
    """Download PAT's Piper voice files."""

    print()
    print(f"Downloading PAT voice: {VOICE_NAME}...")

    try:
        VOICE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        command = [
            sys.executable,
            "-m",
            "piper.download_voices",
            "--data-dir",
            str(VOICE_DIR),
            VOICE_NAME,
        ]

        result = subprocess.run(command)

        if result.returncode != 0:
            failure(
                "PAT voice download failed."
            )
            return False

        if (
            VOICE_MODEL.exists()
            and VOICE_CONFIG.exists()
        ):
            success(
                "PAT voice downloaded successfully."
            )
            return True

        failure(
            "Voice download completed, but the expected "
            "voice files were not found."
        )

        return False

    except Exception as error:
        failure(
            f"Could not download PAT voice: {error}"
        )

        return False

def check_voice_model() -> bool:
    """
    Check whether PAT's Piper voice files exist.

    Offer to download them if they are missing.
    """

    print_header("PAT Voice")

    model_exists = VOICE_MODEL.exists()
    config_exists = VOICE_CONFIG.exists()

    if model_exists:
        success(
            f"Voice model found: {VOICE_MODEL.name}"
        )
    else:
        warning(
            f"Voice model missing: {VOICE_MODEL.name}"
        )

    if config_exists:
        success(
            f"Voice config found: {VOICE_CONFIG.name}"
        )
    else:
        warning(
            f"Voice config missing: {VOICE_CONFIG.name}"
        )

    if model_exists and config_exists:
        return True

    print()

    response = input(
        "Download PAT voice now? [Y/n]: "
    ).strip().lower()

    if response not in {"", "y", "yes"}:
        warning(
            "PAT voice download skipped."
        )
        return False

    return download_voice_model()


# ==========================================================
# MEMORY DATABASE
# ==========================================================

def check_memory_database() -> bool:
    """Check whether PAT's memory database exists."""

    print_header("Memory")

    if MEMORY_DATABASE.exists():
        size = MEMORY_DATABASE.stat().st_size

        success(
            f"Memory database found "
            f"({size:,} bytes)."
        )

        return True

    warning(
        "Memory database does not exist yet."
    )

    return False

# ==========================================================
# PYTHON DEPENDENCIES
# ==========================================================

PACKAGE_IMPORTS = {
    "ollama": "ollama",
    "faster-whisper": "faster_whisper",
    "sounddevice": "sounddevice",
    "numpy": "numpy",
    "piper-tts": "piper",
    "psutil": "psutil",
    "opencv-python": "cv2",
    "pillow": "PIL",
    "pyautogui": "pyautogui",
    "keyboard": "keyboard",
    "mouse": "mouse",
    "pygetwindow": "pygetwindow",
    "requests": "requests",
    "httpx": "httpx",
    "beautifulsoup4": "bs4",
    "python-dotenv": "dotenv",
}


def package_is_installed(import_name: str) -> bool:
    """Return whether a Python module can be imported."""

    return importlib.util.find_spec(import_name) is not None


def check_dependencies() -> bool:
    """Check PAT's important Python dependencies."""

    print_header("Python Dependencies")

    missing_packages: list[str] = []

    for package_name, import_name in PACKAGE_IMPORTS.items():
        if package_is_installed(import_name):
            success(package_name)
        else:
            warning(f"Missing: {package_name}")
            missing_packages.append(package_name)

    if not missing_packages:
        success("All required Python packages are installed.")
        return True

    print()
    print(
        f"Missing packages: {len(missing_packages)}"
    )

    response = input(
        "Install missing packages now? [Y/n]: "
    ).strip().lower()

    if response not in {"", "y", "yes"}:
        warning("Dependency installation skipped.")
        return False

    print()
    print("Installing missing packages...")

    try:
        command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            *missing_packages,
        ]

        result = subprocess.run(command)

        if result.returncode != 0:
            failure(
                "One or more Python packages failed to install."
            )
            return False

    except Exception as error:
        failure(
            f"Dependency installation failed: {error}"
        )
        return False

    print()
    success("Dependency installation completed.")

    still_missing = [
        package_name
        for package_name, import_name
        in PACKAGE_IMPORTS.items()
        if not package_is_installed(import_name)
    ]

    if still_missing:
        failure(
            "Some packages are still missing: "
            + ", ".join(still_missing)
        )
        return False

    success("All Python dependencies are ready.")

    return True



# ==========================================================
# SETUP SUMMARY
# ==========================================================

def run_setup_checks() -> None:
    """Run all PAT setup checks."""

    print()
    print("=" * 60)
    print("PAT OS v0.3 Setup")
    print("Personal AI Technician")
    print("=" * 60)

    checks = {
        "Python": check_python(),
        "Virtual Environment": check_virtual_environment(),
        "Dependencies": check_dependencies(),
        "Directories": check_directories(),
        "Project Files": check_project_files(),
        "Ollama": check_ollama(),
        "PAT AI Model": check_pat_model(),
        "PAT Voice": check_voice_model(),
        "Memory": check_memory_database(),
    }

    print_header("Setup Summary")

    passed = 0

    for name, result in checks.items():
        if result:
            success(name)
            passed += 1
        else:
            warning(name)

    total = len(checks)

    print()
    print(f"Checks passed: {passed}/{total}")

    if passed == total:
        print()
        print("PAT OS is ready.")
    else:
        print()
        print(
            "PAT OS setup found items that need attention."
        )

    print()


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":
    run_setup_checks()