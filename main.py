"""
PAT OS 
Main Entry Point

Supports keyboard mode and hands-free "Hey Pat" wake mode.
"""

from __future__ import annotations
from engines.reminder_engine import reminder_engine
from core.router import route_command
from speech.listen import listen_for_command
from audio.audio_manager import audio_manager
import re
from config import VERSION
import threading
from speech.corrections import correct_transcription

import keyboard
from wakeword.detector import (
    check_for_wake_word,
    listen_for_wake_word,
)
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

def _monitor_barge_in(
    stop_event: threading.Event,
    detected_event: threading.Event,
    command_holder: dict[str, str],
) -> None:
    """
    Listen for 'Hey Pat' while PAT is speaking.

    If the user says a command after the wake phrase,
    preserve it so PAT can execute it immediately.
    """

    while (
        not stop_event.is_set()
        and not audio_manager.is_speaking
    ):
        stop_event.wait(0.05)

    if stop_event.is_set():
        return

    while (
        not stop_event.is_set()
        and audio_manager.is_speaking
    ):
        (
            detected,
            captured_command,
        ) = check_for_wake_word(
            cancel_event=stop_event,
            listen_seconds=2.0,
        )

        if stop_event.is_set():
            return

        if detected:
            command_holder["command"] = (
                captured_command
            )

            detected_event.set()

            stop_speaking()

            print()
            print(
                "[Hey Pat detected during speech]"
            )

            if captured_command:
                print(
                    "Captured command:",
                    captured_command,
                )

            print()

            return

def speak_response(
    text: str,
    allow_barge_in: bool = False,
) -> tuple[bool, str]:
    """
    Speak a PAT response.

    Returns:
        A tuple containing:
        - Whether barge-in occurred
        - Any command captured after "Hey Pat"
    """

    if (
        not allow_barge_in
        or not audio_manager.is_listening
    ):
        success, message = speak(text)

        if not success:
            print(
                f"Voice error: {message}\n"
            )

        return False, ""

    stop_event = threading.Event()
    detected_event = threading.Event()

    command_holder = {
        "command": "",
    }

    monitor_thread = threading.Thread(
        target=_monitor_barge_in,
        args=(
            stop_event,
            detected_event,
            command_holder,
        ),
        daemon=True,
    )

    monitor_thread.start()

    try:
        success, message = speak(text)

    finally:
        stop_event.set()

        monitor_thread.join(
            timeout=1.0
        )

    if not success:
        print(
            f"Voice error: {message}\n"
        )

    return (
        detected_event.is_set(),
        command_holder["command"],
    )

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
    print(f"PAT OS v{VERSION}")
    print("Personal AI Technician")
    print("=" * 50)
    print("System Online\n")

    speak_response("Systems online. Pat is ready.")

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

def process_command(
    command: str,
    allow_barge_in: bool = False,
) -> tuple[bool, bool, str]:
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

    (
        barge_in_detected,
        barge_in_command,
    ) = speak_response(
        spoken_response,
        allow_barge_in=allow_barge_in,
    )

    return (
        result.should_exit,
        barge_in_detected,
        barge_in_command,
    )

def run_keyboard_mode() -> None:
    """Run PAT using typed commands."""

    print("\nKeyboard mode active.")
    print("Type 'exit' to stop PAT.\n")

    while True:
        command = input("You: ").strip()

        if not command:
            continue

        should_exit, _, _ = process_command(
            command
        )

        if should_exit:
            break

def run_wake_mode() -> None:
    """Run PAT using the 'Hey Pat' wake phrase."""

    print("\nWake mode active.")
    print('Say "Hey Pat" to begin.')
    print("Press Ctrl+C to stop PAT.\n")

    success, message = (
        audio_manager.start_input()
    )

    if not success:
        print(
            f"Microphone error: {message}"
        )
        return

    barge_in_pending = False
    barge_in_command = ""

    try:
        while True:
            if not barge_in_pending:
                detected = (
                    listen_for_wake_word()
                )

                if not detected:
                    break

                speak_response("Yes?")

                command = (
                    listen_for_command()
                )

            else:
                barge_in_pending = False

                if barge_in_command:
                    command = (
                        barge_in_command
                    )

                    barge_in_command = ""

                    print(
                        "Barge-in command captured."
                    )

                else:
                    print(
                        "Barge-in accepted. "
                        "Listening for your command."
                    )

                    command = (
                        listen_for_command()
                    )

            if not command:
                message = (
                    "I did not catch that."
                )

                print(
                    f"\nPAT: {message}\n"
                )

                speak_response(
                    message
                )

                continue

            command = correct_transcription(
                command
            )

            print(
                f"\nYou: {command}"
            )

            (
                should_exit,
                barge_in_detected,
                captured_command,
            ) = process_command(
                command,
                allow_barge_in=True,
            )

            if should_exit:
                break

            if barge_in_detected:
                barge_in_pending = True
                barge_in_command = (
                    captured_command
                )

    except KeyboardInterrupt:
        print(
            "\nWake mode stopped."
        )

        speak_response(
            "Shutting down PAT. Goodbye."
        )

    finally:
        audio_manager.stop_input()

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