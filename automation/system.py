"""
PAT OS
automation/system.py

Reads local Windows system information.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import psutil


def _format_bytes(byte_count: int) -> str:
    """Convert bytes into a readable size."""

    gigabytes = byte_count / (1024 ** 3)

    return f"{gigabytes:.1f} gigabytes"


def _format_uptime(total_seconds: float) -> str:
    """Convert uptime seconds into days, hours, and minutes."""

    total_minutes = int(total_seconds // 60)

    days, remaining_minutes = divmod(
        total_minutes,
        1440,
    )

    hours, minutes = divmod(
        remaining_minutes,
        60,
    )

    parts: list[str] = []

    if days:
        parts.append(
            f"{days} day{'s' if days != 1 else ''}"
        )

    if hours:
        parts.append(
            f"{hours} hour{'s' if hours != 1 else ''}"
        )

    if minutes or not parts:
        parts.append(
            f"{minutes} minute{'s' if minutes != 1 else ''}"
        )

    return ", ".join(parts)


def get_system_status() -> tuple[bool, str]:
    """
    Return a spoken summary of CPU, memory, disk,
    battery, and uptime.
    """

    try:
        cpu_usage = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()

        system_drive = Path.home().anchor or "C:\\"
        disk = psutil.disk_usage(system_drive)

        boot_time = datetime.fromtimestamp(
            psutil.boot_time()
        )

        uptime_seconds = (
            datetime.now() - boot_time
        ).total_seconds()

        response_parts = [
            f"CPU usage is {cpu_usage:.0f} percent.",
            (
                f"Memory usage is {memory.percent:.0f} percent, "
                f"using {_format_bytes(memory.used)} "
                f"of {_format_bytes(memory.total)}."
            ),
            (
                f"Your system drive is "
                f"{disk.percent:.0f} percent full."
            ),
            (
                f"System uptime is "
                f"{_format_uptime(uptime_seconds)}."
            ),
        ]

        battery = psutil.sensors_battery()

        if battery is not None:
            charging_status = (
                "and charging"
                if battery.power_plugged
                else "and running on battery"
            )

            response_parts.append(
                f"Battery is at {battery.percent:.0f} percent "
                f"{charging_status}."
            )

        return True, " ".join(response_parts)

    except Exception as error:
        return (
            False,
            f"I could not read the system status: {error}",
        )


if __name__ == "__main__":
    success, message = get_system_status()

    print(message)
    print(f"Success: {success}")