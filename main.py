"""
PAT OS 1.0
Main Entry Point
"""

from core.router import route_command


def startup():
    print("=" * 50)
    print("PAT OS 1.0")
    print("Personal AI Technician")
    print("=" * 50)
    print("System Online\n")


def main():

    startup()

    while True:

        command = input("You: ").strip()

        if not command:
            continue

        result = route_command(command)

        print(f"\nPAT: {result.response}\n")

        if result.should_exit:
            break


if __name__ == "__main__":
    main()