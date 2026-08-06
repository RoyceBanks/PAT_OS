PAT OS User Guide

This guide covers the commands currently supported by PAT OS v0.1.0.

PAT is still an alpha project. Interaction is currently text-based.

1. Starting PAT

Open a terminal in the PAT_OS folder.

Activate the virtual environment:

.\.venv\Scripts\Activate.ps1

Start PAT:

python main.py

PAT should display its startup message and a prompt:

You:

2. Asking General Questions

Type a normal question:

Who are you?

Explain how a CPU works.

Help me understand Python functions.

Questions that do not match a built-in command are sent to PAT's local Ollama model.

3. Opening Applications

PAT can open approved applications configured in automation/apps.py.

Examples:

open notepad

launch calculator

start chrome

run visual studio code

Supported names depend on the current APP_PATHS configuration.

Common configured applications may include:

Notepad

Calculator

File Explorer

Task Manager

Chrome

Microsoft Edge

Discord

Steam

Visual Studio Code

If PAT recognizes the application but cannot find it, the executable path may need to be updated.

4. Saving Memories

Use this format:

remember my favorite game is Halo

Other examples:

remember my work folder is C:\Work

remember my preferred editor is VS Code

PAT stores the information in:

data/memory.db

Saving the same memory key again updates the old value.

Example:

remember my favorite game is Halo 3

5. Recalling Memories

Ask:

what is my favorite game

or:

what's my preferred editor

PAT reads the value from its SQLite database.

The wording after my must currently match the saved memory key closely.

6. Exiting PAT

Use one of the supported exit commands:

exit

quit

goodbye

close pat

PAT will stop safely and return to the terminal.

7. Current Task Engine

PAT contains a task engine, but general multi-command planning is not connected to normal user input yet.

The engine can currently be tested with:

python -m engines.task_engine

This test queues approved application-launch tasks and runs them in order.

Natural multi-step requests are planned for a future release.

8. Current Limitations

The following features are not yet complete:

Speaking responses aloud

Listening through the microphone

Wake phrase detection

Timers and scheduled reminders

Email and calendar access

Browser navigation

Phone control

Camera analysis

Desktop dashboard

Helmet integration

A folder existing in the repository does not mean that feature is already operational.

9. Privacy

Current memory and conversation processing are local when Ollama is used.

Be careful when saving sensitive information. Do not store:

Passwords

Banking information

Authentication tokens

Private keys

Recovery codes

PAT's current memory database is not encrypted.

10. Troubleshooting

PAT says it cannot contact its AI engine

Test Ollama:

ollama run pat

Confirm the model exists:

ollama list

PAT opens the wrong application

Review the aliases in:

automation/apps.py

PAT cannot find an application

Update that application's executable path in APP_PATHS.

PAT does not remember something

Use the exact format:

remember my KEY is VALUE

Then ask:

what is my KEY

PAT starts from the wrong folder

Navigate to the repository root before running:

cd C:\Path\To\PAT_OS
python main.py

11. Recommended Backup Routine

At each stable milestone:

git add .
git commit -m "Describe the completed milestone"
git push

Also keep an occasional ZIP backup that excludes .venv.