"""
PAT OS
brain/ai.py

Local Ollama conversation engine.
"""

import ollama

from config import (
    AI_CONVERSATION_TURNS,
    OLLAMA_MODEL,
    SYSTEM_PROMPT,
)


class AIBrain:

    def __init__(self):

        self.messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]

        print("PAT AI initialized.")

    def _trim_history(self) -> None:
        """
        Keep only the most recent conversation turns.

        One turn consists of:
            user message
            assistant response
        """

        maximum_messages = (
            AI_CONVERSATION_TURNS * 2
        )

        conversation = self.messages[1:]

        if len(conversation) <= maximum_messages:
            return

        self.messages = [
            self.messages[0],
            *conversation[-maximum_messages:],
        ]

    def ask(self, prompt: str) -> str:
        """
        Send a prompt to the AI and return the response.
        """

        self.messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        try:

            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=self.messages,
            )

            answer = response[
                "message"
            ]["content"]

            self.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
            )

            self._trim_history()

            return answer

        except Exception as error:

            # Remove the unanswered user message so
            # a failed Ollama request does not pollute
            # the next conversation.
            if (
                self.messages
                and self.messages[-1].get("role")
                == "user"
            ):
                self.messages.pop()

            return (
                "I encountered an error talking "
                "to my AI engine.\n"
                f"{error}"
            )

    def reset_memory(
        self,
        quiet: bool = False,
    ) -> None:
        """
        Clear the temporary AI conversation.
        """

        self.messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]

        if not quiet:
            print(
                "Conversation memory cleared."
            )


brain = AIBrain()


def ask_ai(prompt: str) -> str:
    return brain.ask(prompt)


def reset_ai_conversation(
    quiet: bool = False,
) -> None:
    """Clear PAT's temporary Ollama conversation."""

    brain.reset_memory(
        quiet=quiet
    )