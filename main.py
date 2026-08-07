"""
PAT OS v0.2
Main Entry Point

Supports keyboard mode and hands-free "Hey Pat" wake mode.
"""

from __future__ import annotations

from core.router import route_command
from speech.listen import listen_for_command
from voice.speak import speak
from wakeword.detector import listen_for_wake_word


def speak_response(text: str) -> None:
    """Speak PAT's response and show voice errors."""

    success, message = speak(text)

    if not success:
        print(f"Voice error: {message}\n")


def startup() -> None:
    """Display and announce PAT's startup status."""

    print("=" * 50)
    print("PAT OS v0.2")
    print("Personal AI Technician")
    print("=" * 50)
    print("System Online\n")

    speak_response("Systems online. PAT is ready.")


def process_command(command: str) -> bool:
    """
    Process one command.

    Returns:
        True when PAT should shut down.
    """

    result = route_command(command)

    print(f"\nPAT: {result.response}\n")

    speak_response(result.response)

    return result.should_exit


def run_keyboard_mode() -> None:
    """Run PAT using typed commands."""

    print("\nKeyboard mode active.")
    print("Type 'exit' to stop PAT.\n")

    while True:
        command = input("You: ").strip()

        if not command:
            continue

        if process_command(command):
            break


def run_wake_mode() -> None:
    """Run PAT using the 'Hey Pat' wake phrase."""

    print("\nWake mode active.")
    print('Say "Hey Pat" to begin.')
    print("Press Ctrl+C to stop PAT.\n")

    try:
        while True:
            detected = listen_for_wake_word()

            if not detected:
                break

            speak_response("Yes?")

            command = listen_for_command()

            if not command:
                message = "I did not catch that."

                print(f"\nPAT: {message}\n")
                speak_response(message)
                continue

            print(f"\nYou: {command}")

            if process_command(command):
                break

    except KeyboardInterrupt:
        print("\nWake mode stopped.")

        speak_response("Shutting down PAT. Goodbye.")


def main() -> None:
    """Start PAT in keyboard mode or wake mode."""

    startup()

    mode = input(
        "Press Enter for wake mode, "
        "or type T for keyboard mode: "
    ).strip().lower()

    if mode == "t":
        run_keyboard_mode()
    else:
        run_wake_mode()


if __name__ == "__main__":
    main()