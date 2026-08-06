PAT OS Internal API Reference

This document describes the current Python interfaces used by PAT OS v0.1.0.

This is an internal module reference, not a network or REST API.

automation.apps

normalize_app_name

def normalize_app_name(app_name: str) -> str

Normalizes a requested application name and resolves known aliases.

Example:

normalize_app_name("VS Code")

Possible result:

vscode

open_application

def open_application(app_name: str) -> tuple[bool, str]

Opens an approved application.

Parameters:

app_name: User-facing application name or alias

Returns:

bool: Whether PAT successfully started the process

str: A user-facing result message

Example:

success, message = open_application("notepad")

Example success:

(True, "Opening notepad.")

brain.ai

AIBrain

class AIBrain

Maintains the active conversation and communicates with Ollama.

ask

def ask(self, prompt: str) -> str

Sends a prompt to the configured Ollama model and returns its text response.

reset_memory

def reset_memory(self) -> None

Clears the in-memory conversation history while preserving the configured system prompt.

ask_ai

def ask_ai(prompt: str) -> str

Convenience wrapper around the shared AIBrain instance.

brain.memory

MemoryManager

class MemoryManager

Manages PAT's persistent SQLite key-value memory.

save

def save(
    self,
    memory_key: str,
    memory_value: str,
) -> tuple[bool, str]

Creates or updates a memory.

get

def get(self, memory_key: str) -> str | None

Returns the stored value or None.

delete

def delete(self, memory_key: str) -> tuple[bool, str]

Deletes a memory by key.

list_all

def list_all(self) -> list[dict[str, str]]

Returns all memories with keys, values, and update timestamps.

Convenience functions

def save_memory(
    memory_key: str,
    memory_value: str,
) -> tuple[bool, str]

def get_memory(memory_key: str) -> str | None

def delete_memory(memory_key: str) -> tuple[bool, str]

def list_memories() -> list[dict[str, str]]

core.router

Intent

class Intent(Enum)

Represents the request type detected by PAT.

Current values include:

OPEN_APPLICATION

SAVE_MEMORY

GET_MEMORY

EXIT

GENERAL_AI

RouteResult

@dataclass
class RouteResult:
    intent: Intent
    response: str
    success: bool = True
    should_exit: bool = False

Standard result returned by the router.

clean_command

def clean_command(command: str) -> str

Normalizes spacing and case before intent detection.

extract_application_name

def extract_application_name(command: str) -> str | None

Extracts an application from supported launch-command patterns.

extract_memory

def extract_memory(command: str)

Extracts a memory key and optional value from supported memory phrases.

detect_intent

def detect_intent(command: str)

Determines the command intent and any extracted value.

route_command

def route_command(command: str) -> RouteResult

Routes a complete user command to automation, memory, exit handling, or the local AI.

engines.task_engine

TaskStatus

class TaskStatus(Enum)

Values:

PENDING

RUNNING

COMPLETED

FAILED

CANCELLED

Task

@dataclass
class Task

Important fields:

name

action

arguments

task_id

status

result

error

created_at

started_at

completed_at

TaskEngine

class TaskEngine

register_handler

def register_handler(
    self,
    action: str,
    handler: TaskHandler,
) -> None

Connects an action name to a Python function.

create_task

def create_task(
    self,
    name: str,
    action: str,
    **arguments,
) -> Task

Creates and queues a task.

cancel_task

def cancel_task(self, task_id: str) -> tuple[bool, str]

Cancels a pending task.

execute_task

def execute_task(self, task: Task) -> Task

Runs one task through its registered handler.

run_next

def run_next(self) -> Task | None

Runs the next queued task.

run_all

def run_all(self) -> list[Task]

Runs all queued tasks in order.

get_pending_tasks

def get_pending_tasks(self) -> list[Task]

Returns pending tasks.

get_history

def get_history(self) -> list[Task]

Returns session task history.

Shared engine instance

task_engine = TaskEngine()

Modules may import this shared instance when a single central task queue is desired.

Compatibility Notes

This reference describes the current working v0.1.0 implementation.

Interfaces may change during alpha development. Update this file whenever a public function, class, return type, or module path changes.