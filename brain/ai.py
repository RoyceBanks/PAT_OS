"""
==========================================================
PAT OS v0.1
brain/ai.py

Local AI Brain
Powered by Ollama
==========================================================
"""

import ollama
from config import (
    OLLAMA_MODEL,
    SYSTEM_PROMPT,
)


class AIBrain:

    def __init__(self):

        self.messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]

        print("PAT AI initialized.")

    def ask(self, prompt: str) -> str:
        """
        Send a prompt to the AI and return the response.
        """

        self.messages.append(
            {
                "role": "user",
                "content": prompt
            }
        )

        try:

            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=self.messages
            )

            answer = response["message"]["content"]

            self.messages.append(
                {
                    "role": "assistant",
                    "content": answer
                }
            )

            return answer

        except Exception as error:

            return f"I encountered an error talking to my AI engine.\n{error}"

    def reset_memory(self):
        """
        Clears the current conversation.
        """

        self.messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]

        print("Conversation memory cleared.")


brain = AIBrain()


def ask_ai(prompt: str):

    return brain.ask(prompt)