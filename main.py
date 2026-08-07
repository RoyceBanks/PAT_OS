"""
PAT OS v0.2
Main Entry Point

Supports typed commands and push-to-talk voice commands.
PAT displays and speaks every response.
"""

from core.router import route_command
from speech.listen import listen
from voice.speak import speak


def speak_response(text: str) -> None:
    """Speak PAT's response and display voice errors."""

    success, message = speak(text)

    if not success:
        print(f"Voice error: {message}\n")


def startup() -> None:
    """Start PAT and announce system status."""

    print("=" * 50)
    print("PAT OS v0.2")
    print("Personal AI Technician")
    print("=" * 50)
    print("System Online\n")

    speak_response("Systems online. PAT is ready.")


def get_command() -> str:
    """
    Get either a typed command or a spoken command.

    Type V to activate push-to-talk.
    """

    user_input = input(
        "Type a command, or enter V for voice: "
    ).strip()

    if user_input.lower() == "v":
        command = listen().strip()

        if not command:
            message = "I did not catch that."
            print(f"\nPAT: {message}\n")
            speak_response(message)
            return ""

        print(f"\nYou (voice): {command}")

        return command

    return user_input


def main() -> None:
    """Run PAT's main interaction loop."""

    startup()

    while True:
        command = get_command()

        if not command:
            continue

        result = route_command(command)

        print(f"\nPAT: {result.response}\n")

        speak_response(result.response)

        if result.should_exit:
            break


if __name__ == "__main__":
    main()