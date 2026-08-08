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

def get_process_details(
    application: str,
) -> tuple[bool, str]:
    """Return PID and memory information for an application."""

    try:
        application = (
            application.strip().lower()
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

        matches = []

        for process in psutil.process_iter(
            [
                "pid",
                "name",
                "memory_info",
            ]
        ):
            try:
                name = process.info["name"]

                if (
                    not name
                    or name.casefold()
                    not in expected_names
                ):
                    continue

                memory_info = process.info[
                    "memory_info"
                ]

                memory_bytes = (
                    memory_info.rss
                    if memory_info
                    else 0
                )

                matches.append(
                    (
                        process.info["pid"],
                        memory_bytes,
                    )
                )

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue

        if not matches:
            return (
                False,
                f"{application.title()} is not running.",
            )

        total_memory = sum(
            memory
            for _, memory in matches
        )

        memory_mb = (
            total_memory
            / (1024 ** 2)
        )

        pids = [
            str(pid)
            for pid, _ in matches
        ]

        if len(pids) == 1:
            pid_text = (
                f"Its PID is {pids[0]}."
            )
        else:
            pid_text = (
                f"It has {len(pids)} processes "
                f"with PIDs {', '.join(pids)}."
            )

        return (
            True,
            (
                f"{application.title()} is using about "
                f"{memory_mb:.0f} megabytes of memory. "
                f"{pid_text}"
            ),
        )

    except Exception as error:
        return (
            False,
            f"I could not get process details: {error}",
        )

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


def get_top_memory_process_names(
    limit: int = 5,
) -> list[str]:
    """Return ordered process names from the latest memory ranking."""

    return [
        name
        for name, _
        in _collect_top_memory_processes(limit)
    ]

def get_top_memory_processes(
    
    limit: int = 5,
) -> tuple[bool, str]:
    """Return applications using the most physical memory."""

    try:
        top = _collect_top_memory_processes(
            limit
        )

        if not top:
            return (
                False,
                "I could not find any running processes.",
            )

        descriptions = []

        for number, (
            name,
            memory_bytes,
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
) -> tuple[bool, str, list[str]]:
    """Return top CPU processes and their ordered names."""

    try:
        top = _collect_top_cpu_processes(
            limit
        )

        if not top:
            return (
                True,
                "No processes are using significant CPU right now.",
                [],
            )

        descriptions = []

        process_names = []

        for number, (
            name,
            cpu,
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

            process_names.append(
                name
            )

        return (
            True,
            (
                f"The top {len(top)} processes by CPU are: "
                + ". ".join(descriptions)
                + "."
            ),
            process_names,
        )

    except Exception as error:
        return (
            False,
            f"I could not read process CPU usage: {error}",
            [],
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

def _collect_top_memory_processes(
    limit: int = 5,
) -> list[tuple[str, int]]:
    """Collect top processes by memory, grouped by executable name."""

    totals: dict[str, int] = {}

    for process in psutil.process_iter(
        [
            "name",
            "memory_info",
        ]
    ):
        try:
            name = process.info["name"]
            memory_info = process.info["memory_info"]

            if not name or memory_info is None:
                continue

            key = name.casefold()

            totals[key] = (
                totals.get(key, 0)
                + memory_info.rss
            )

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
        ):
            continue

    results = [
        (
            name,
            memory_bytes,
        )
        for name, memory_bytes
        in totals.items()
    ]

    results.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    return results[:limit]

def _collect_top_cpu_processes(
    limit: int = 5,
) -> list[tuple[str, float]]:
    """Collect top CPU processes, grouped by executable name."""

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

    time.sleep(
        0.5
    )

    totals: dict[str, float] = {}

    for process in processes:
        try:
            name = process.name()

            if not name:
                continue

            cpu = process.cpu_percent(
                interval=None
            )

            if cpu <= 0:
                continue

            key = name.casefold()

            totals[key] = (
                totals.get(key, 0.0)
                + cpu
            )

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
        ):
            continue

    results = list(
        totals.items()
    )

    results.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    return results[:limit] 