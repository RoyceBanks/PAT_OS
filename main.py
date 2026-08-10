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
from brain.ai import reset_ai_conversation
import re
from config import VERSION, WAKE_PHRASE
import threading
from speech.corrections import correct_transcription

from brain.session_context import (
    clear_session_context,
    remember_turn,
)


import keyboard
from wakeword.detector import (
    capture_barge_in_continuation,
    check_for_wake_word,
    listen_for_wake_word
)
from config import (
    SPEECH_MAX_CHARS,
    SPEECH_MAX_SENTENCES,
    CONVERSATION_FOLLOW_UP_SECONDS,
    WAKE_PHRASE,
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

def _looks_like_pat_self_audio(
    pat_text: str,
    captured_command: str,
) -> bool:
    """
    Reject likely wake detections caused by PAT's own speech.
    """

    pat_words = (
        pat_text.casefold()
        .replace(",", " ")
        .replace(".", " ")
        .replace("?", " ")
        .replace("!", " ")
        .split()
    )

    command_words = (
        captured_command.casefold()
        .split()
    )

    # A real command following "Hey Pat" should usually
    # contain something PAT is not currently saying.
    if not command_words:
        return False

    command_text = " ".join(
        command_words
    )

    pat_normalized = " ".join(
        pat_words
    )

    return (
        len(command_words) >= 2
        and command_text in pat_normalized
    )

def _monitor_barge_in(
    stop_event: threading.Event,
    detected_event: threading.Event,
    command_holder: dict[str, str],
    pat_text: str,
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
    # Start barge-in monitoring with a fresh buffer.
    audio_manager.flush_input()
    while (
        not stop_event.is_set()
        and audio_manager.is_speaking
    ):
        (
            detected,
            captured_command,
        ) = check_for_wake_word(
            cancel_event=stop_event,
            listen_seconds=1.0,
        )

        if stop_event.is_set():
            return

        if detected:
            if _looks_like_pat_self_audio(
                pat_text,
                captured_command,
            ):
                print(
                    "[Ignored likely PAT self-audio]"
                )
                continue
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

def _contains_wake_phrase(
    text: str,
) -> bool:
    """Return whether PAT's own speech contains its wake phrase."""

    normalized_text = " ".join(
        text.casefold().split()
    )

    normalized_wake = " ".join(
        WAKE_PHRASE.casefold().split()
    )

    return normalized_wake in normalized_text

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
        or _contains_wake_phrase(text)
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
            text,
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

    remember_turn(
        user_command=command,
        response=result.response,
        intent=result.intent.name,
    )

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

def merge_barge_in_command(
    first_part: str,
    continuation: str,
) -> str:
    """
    Merge overlapping Whisper transcriptions.

    Example:
        "what time is it"
        + "it"
        -> "what time is it"

        "explain the difference between ram"
        + "ram and storage"
        -> "explain the difference between ram and storage"
    """

    first_words = first_part.strip().split()
    continuation_words = continuation.strip().split()

    if not first_words:
        return " ".join(continuation_words)

    if not continuation_words:
        return " ".join(first_words)

    maximum_overlap = min(
        len(first_words),
        len(continuation_words),
    )

    overlap = 0

    for size in range(
        maximum_overlap,
        0,
        -1,
    ):
        first_tail = [
            word.casefold()
            for word in first_words[-size:]
        ]

        continuation_head = [
            word.casefold()
            for word in continuation_words[:size]
        ]

        if first_tail == continuation_head:
            overlap = size
            break

    merged_words = (
        first_words
        + continuation_words[overlap:]
    )

    return " ".join(merged_words)


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
    follow_up_pending = False

    try:
        while True:
            if follow_up_pending:
                follow_up_pending = False

                
                command = listen_for_command(
                    start_timeout=(
                        CONVERSATION_FOLLOW_UP_SECONDS
                    ),
                    quiet=True,
                )

                if not command:
                    reset_ai_conversation(
                        quiet=True
                    )

                    clear_session_context()

                    print(
                        "\nConversation window closed."
                    )

                    continue

            elif not barge_in_pending:
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
                continuation = (
                    capture_barge_in_continuation(
                        max_seconds=6.0
                    )
                )

                barge_in_command = (
                    merge_barge_in_command(
                        captured_command,
                        continuation,
                    )
                )

                print(
                    "Merged barge-in command:",
                    barge_in_command,
                )

                barge_in_pending = True
                follow_up_pending = False

                if continuation:
                    print(
                        "Captured continuation:",
                        continuation,
                    )

            else:
                barge_in_pending = False
                follow_up_pending = True

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