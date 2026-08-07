"""
PAT OS v0.2
Main Entry Point

Supports keyboard mode and hands-free "Hey Pat" wake mode.
"""

from __future__ import annotations
from engines.reminder_engine import reminder_engine
from core.router import route_command
from speech.listen import listen_for_command
import re
from wakeword.detector import listen_for_wake_word
import keyboard
from config import (
    SPEECH_MAX_CHARS,
    SPEECH_MAX_SENTENCES,
)
from voice.speak import (
    speak,
    stop_speaking,
)


def stop_pat_speech() -> None:
    """Stop PAT's current spoken response."""

    stop_speaking()

    print()
    print("[PAT speech stopped]")
    print()

def speak_response(text: str) -> None:
    """Speak PAT's response and show voice errors."""

    success, message = speak(text)

    if not success:
        print(f"Voice error: {message}\n")

def reminder_alert(message: str) -> None:
    """Display and speak a reminder when it becomes due."""

    print()
    print("=" * 50)
    print(f"PAT: {message}")
    print("=" * 50)
    print()

    speak_response(message)

def startup() -> None:
    """Display and announce PAT's startup status."""

    reminder_engine.set_callback(
        reminder_alert
    )

    reminder_engine.start()

    keyboard.add_hotkey(
        "esc",
        stop_pat_speech,
    )


    print("=" * 50)
    print("PAT OS v0.4")
    print("Personal AI Technician")
    print("=" * 50)
    print("System Online\n")

    speak_response("Systems online. PAT is ready.")

def prepare_spoken_response(text: str) -> str:
    """
    Shorten long responses for speech.

    The full response is still printed
    to the console.
    """

    if len(text) <= SPEECH_MAX_CHARS:
        return text

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text.strip(),
    )

    spoken_sentences: list[str] = []
    current_length = 0

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        if len(spoken_sentences) >= SPEECH_MAX_SENTENCES:
            break

        new_length = (
            current_length
            + len(sentence)
        )

        if (
            new_length > SPEECH_MAX_CHARS
            and spoken_sentences
        ):
            break

        spoken_sentences.append(
            sentence
        )

        current_length = new_length

    spoken_text = " ".join(
        spoken_sentences
    )

    if not spoken_text:
        spoken_text = text[
            :SPEECH_MAX_CHARS
        ].rsplit(
            " ",
            1,
        )[0]

    return (
        spoken_text
        + " I printed the full answer "
        + "to the console."
    )

def process_command(command: str) -> bool:
    """
    Process one command.

    Returns:
        True when PAT should shut down.
    """

    result = route_command(command)

    print(f"\nPAT: {result.response}\n")

    spoken_response = prepare_spoken_response(
        result.response
    )

    speak_response(
        spoken_response
    )

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