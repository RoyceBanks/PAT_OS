"""
PAT OS
automation/process_monitor.py

Read-only Windows system and process monitoring.
"""

from __future__ import annotations

import time

import psutil


PROCESS_ALIASES = {
    "discord": (
        "discord.exe",
    ),
    "firefox": (
        "firefox.exe",
    ),
    "steam": (
        "steam.exe",
        "steamwebhelper.exe",
    ),
    "ollama": (
        "ollama.exe",
    ),
    "visual studio code": (
        "code.exe",
    ),
    "vs code": (
        "code.exe",
    ),
    "vscode": (
        "code.exe",
    ),
    "notepad": (
        "notepad.exe",
    ),
    "calculator": (
        "calculatorapp.exe",
        "calculator.exe",
    ),
}


def get_system_usage() -> tuple[bool, str]:
    """Return current CPU and memory usage."""

    try:
        cpu = psutil.cpu_percent(
            interval=0.4
        )

        memory = psutil.virtual_memory()

        used_gb = memory.used / (1024 ** 3)
        total_gb = memory.total / (1024 ** 3)
        available_gb = memory.available / (1024 ** 3)

        message = (
            f"CPU usage is {cpu:.0f} percent. "
            f"Memory usage is {memory.percent:.0f} percent. "
            f"{used_gb:.1f} of {total_gb:.1f} gigabytes are in use, "
            f"with {available_gb:.1f} gigabytes available."
        )

        return True, message

    except Exception as error:
        return (
            False,
            f"I could not read system usage: {error}",
        )


def get_cpu_usage() -> tuple[bool, str]:
    """Return current total CPU usage."""

    try:
        cpu = psutil.cpu_percent(
            interval=0.4
        )

        return (
            True,
            f"CPU usage is {cpu:.0f} percent.",
        )

    except Exception as error:
        return (
            False,
            f"I could not read CPU usage: {error}",
        )


def get_memory_usage() -> tuple[bool, str]:
    """Return current memory information."""

    try:
        memory = psutil.virtual_memory()

        used_gb = memory.used / (1024 ** 3)
        total_gb = memory.total / (1024 ** 3)
        available_gb = memory.available / (1024 ** 3)

        return (
            True,
            (
                f"Memory usage is {memory.percent:.0f} percent. "
                f"{used_gb:.1f} of {total_gb:.1f} gigabytes "
                f"are in use. "
                f"{available_gb:.1f} gigabytes are available."
            ),
        )

    except Exception as error:
        return (
            False,
            f"I could not read memory usage: {error}",
        )


def _process_display_name(
    name: str | None,
) -> str:
    """Make Windows executable names easier to speak."""

    if not name:
        return "Unknown process"

    if name.lower().endswith(".exe"):
        return name[:-4]

    return name


def get_top_memory_processes(
    limit: int = 5,
) -> tuple[bool, str]:
    """Return processes using the most physical memory."""

    try:
        processes = []

        for process in psutil.process_iter(
            [
                "pid",
                "name",
                "memory_info",
            ]
        ):
            try:
                memory_info = process.info[
                    "memory_info"
                ]

                if memory_info is None:
                    continue

                processes.append(
                    (
                        memory_info.rss,
                        process.info["name"],
                    )
                )

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue

        processes.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        top = processes[:limit]

        if not top:
            return (
                False,
                "I could not find any running processes.",
            )

        descriptions = []

        for number, (
            memory_bytes,
            name,
        ) in enumerate(
            top,
            start=1,
        ):
            memory_mb = (
                memory_bytes
                / (1024 ** 2)
            )

            descriptions.append(
                (
                    f"{number}. "
                    f"{_process_display_name(name)}, "
                    f"{memory_mb:.0f} megabytes"
                )
            )

        return (
            True,
            (
                f"The top {len(top)} processes by memory are: "
                + ". ".join(descriptions)
                + "."
            ),
        )

    except Exception as error:
        return (
            False,
            f"I could not read process memory usage: {error}",
        )


def get_top_cpu_processes(
    limit: int = 5,
) -> tuple[bool, str]:
    """Return processes currently using the most CPU."""

    try:
        processes = []

        for process in psutil.process_iter(
            [
                "pid",
                "name",
            ]
        ):
            try:
                process.cpu_percent(
                    interval=None
                )

                processes.append(
                    process
                )

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue

        # CPU percentages need two samples.
        time.sleep(0.5)

        results = []

        for process in processes:
            try:
                cpu = process.cpu_percent(
                    interval=None
                )

                if cpu <= 0:
                    continue

                results.append(
                    (
                        cpu,
                        process.name(),
                    )
                )

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue

        results.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        top = results[:limit]

        if not top:
            return (
                True,
                "No processes are using significant CPU right now.",
            )

        descriptions = []

        for number, (
            cpu,
            name,
        ) in enumerate(
            top,
            start=1,
        ):
            descriptions.append(
                (
                    f"{number}. "
                    f"{_process_display_name(name)}, "
                    f"{cpu:.0f} percent"
                )
            )

        return (
            True,
            (
                f"The top {len(top)} processes by CPU are: "
                + ". ".join(descriptions)
                + "."
            ),
        )

    except Exception as error:
        return (
            False,
            f"I could not read process CPU usage: {error}",
        )


def is_process_running(
    application: str,
) -> tuple[bool, str]:
    """Check whether an application/process is currently running."""

    try:
        application = (
            application.strip().lower()
        )

        if not application:
            return (
                False,
                "You did not give me an application name.",
            )

        expected_names = PROCESS_ALIASES.get(
            application,
            (
                application,
                f"{application}.exe",
            ),
        )

        expected_names = {
            name.casefold()
            for name in expected_names
        }

        for process in psutil.process_iter(
            ["name"]
        ):
            try:
                name = process.info["name"]

                if (
                    name
                    and name.casefold()
                    in expected_names
                ):
                    return (
                        True,
                        f"{application.title()} is running.",
                    )

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue

        return (
            True,
            f"{application.title()} is not running.",
        )

    except Exception as error:
        return (
            False,
            f"I could not check that process: {error}",
        )
    