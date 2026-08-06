PAT OS Developer Guide

This guide explains how to work on PAT OS without breaking its modular design.

1. Development Setup

Follow installation.md before making code changes.

Activate the virtual environment:

.\.venv\Scripts\Activate.ps1

Run PAT:

python main.py

Run component tests:

python -m automation.apps
python -m brain.memory
python -m core.router
python -m engines.task_engine

2. Git Workflow

Before starting work:

git status
git pull

Create a feature branch:

git checkout -b feature/feature-name

After testing:

git add .
git commit -m "Added feature name"
git push -u origin feature/feature-name

Use milestone tags for completed releases:

git tag -a v0.2.0 -m "Voice interaction milestone"
git push origin v0.2.0

Do not commit:

.venv/

__pycache__/

Large downloaded models

Private credentials

Temporary log files

Personal database content unless intentionally creating test fixtures

3. Coding Standards

Use:

Python type hints

PEP 8 naming

Clear docstrings

Small functions

Explicit error handling

Descriptive names

Example:

def open_application(app_name: str) -> tuple[bool, str]:
    """Open an approved application and return its result."""

Avoid:

def do_it(x):
    pass

4. Return Values

Action handlers should normally return:

tuple[bool, str]

Example:

return True, "Opening notepad."

or:

return False, "I could not locate notepad."

This format lets the router, task engine, voice system, and dashboard use the same result.

5. Adding an Application

Open:

automation/apps.py

Add the application to APP_PATHS:

APP_PATHS = {
    "example app": [
        r"C:\Path\To\Example.exe",
    ],
}

Optional alias:

ALIASES = {
    "example": "example app",
}

Test:

python -m automation.apps

Then enter the configured name.

6. Adding a New Intent

Open:

core/router.py

Step 1: Add the intent

class Intent(Enum):
    NEW_ACTION = auto()

Step 2: Detect it

Create a focused parsing function:

def extract_new_action(command: str) -> str | None:
    ...

Use it inside detect_intent().

Step 3: Route it

Handle it inside route_command():

if intent is Intent.NEW_ACTION:
    ...

Step 4: Test it

Test positive, negative, and malformed commands.

Do not route dangerous operations directly without confirmation.

7. Adding a Task Handler

Import the task engine:

from engines.task_engine import task_engine

Register a handler:

task_engine.register_handler(
    "open_application",
    open_application,
)

Create a task:

task_engine.create_task(
    name="Open Notepad",
    action="open_application",
    app_name="notepad",
)

Execute it:

task = task_engine.run_next()

Handlers must accept keyword arguments that match the task's arguments dictionary.

8. Adding a Skill

Skills are independent capabilities such as weather, calculator, timers, or music control.

A future skill should expose a predictable interface:

class ExampleSkill:
    name = "example"

    def can_handle(self, command: str) -> bool:
        ...

    def execute(self, command: str) -> tuple[bool, str]:
        ...

Until the plugin loader is implemented, register skills explicitly through the router or an engine.

9. Database Changes

Current memory uses SQLite.

Before changing the schema:

Back up data/memory.db.

Document the schema change.

Add a migration strategy.

Test with an empty database.

Test with an existing database.

Never assume every user has a fresh database.

10. Configuration

Project-wide values belong in config.py.

Good candidates:

Paths

Thresholds

Model names

Feature flags

Device indexes

Limits

Do not store secrets directly in config.py.

Future API keys should be loaded from environment variables or a local .env file that is excluded from Git.

11. Logging

Early development currently uses console output in some modules.

New persistent logging should use Python's logging module.

Recommended levels:

DEBUG: development detail

INFO: normal lifecycle and actions

WARNING: recoverable problems

ERROR: failed operations

CRITICAL: PAT cannot continue safely

Never log passwords, authentication tokens, or private message contents by default.

12. Testing

The current repository uses simple module tests. The long-term target is pytest.

Recommended structure:

tests/
├── test_apps.py
├── test_memory.py
├── test_router.py
└── test_task_engine.py

Each feature should test:

Expected success

Expected failure

Empty input

Invalid input

Exceptions

Persistent behavior where applicable

Avoid tests that depend on a specific personal file path unless the path is mocked.

13. Error Handling

Avoid broad silent exceptions:

try:
    ...
except:
    pass

Use:

try:
    ...
except OSError as error:
    return False, f"Operation failed: {error}"

Errors shown to the user should be understandable. Detailed technical information can be written to logs.

14. Security Rules

Do not add code that:

Executes arbitrary model-generated shell commands

Downloads and runs files without confirmation

Stores plaintext credentials

Disables security tools

Sends messages without user approval

Deletes files without confirmation and recovery options

The user must remain in control of consequential actions.

15. Definition of Done

A feature is complete when:

It works from the normal PAT entry point

Failure states are handled

It follows the existing module structure

It does not falsely report success

It has a test or repeatable test procedure

Documentation is updated

Changes are committed to Git