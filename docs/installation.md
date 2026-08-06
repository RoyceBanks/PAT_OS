PAT OS Installation Guide

This guide covers the current Windows installation process for PAT OS v0.1.0.

PAT OS is under active development. Version 0.1.0 currently supports typed commands, local AI through Ollama, application launching, persistent memory, and task execution.

1. Requirements

Operating system

Windows 10 or Windows 11

64-bit Python installation

Recommended hardware

16 GB RAM minimum

32 GB RAM recommended

A modern six-core CPU or better

An NVIDIA or AMD GPU is optional, but can improve local-model performance

At least 10 GB of free storage for PAT OS, Python packages, and local AI models

Required software

Python 3.11 or newer

Git

Ollama

Visual Studio Code or another code editor

2. Clone the Repository

Open PowerShell or Command Prompt and run:

git clone https://github.com/YOUR_USERNAME/PAT_OS.git
cd PAT_OS

Replace YOUR_USERNAME with the GitHub account that hosts the repository.

3. Create a Virtual Environment

From the root PAT_OS folder:

python -m venv .venv

Activate it in PowerShell:

.\.venv\Scripts\Activate.ps1

Activate it in Command Prompt:

.venv\Scripts\activate.bat

When activation succeeds, the terminal prompt begins with:

(.venv)

4. Install Python Dependencies

With the virtual environment active:

python -m pip install --upgrade pip
pip install -r requirements.txt

If a package fails to install, copy the complete error message before changing the requirements file.

5. Install Ollama

Install Ollama for Windows from its official installer.

Verify the installation:

ollama --version

Ollama is a system application. It does not need to be installed inside the Python virtual environment.

6. Download the Base Model

PAT currently uses Qwen through Ollama.

ollama pull qwen3

Confirm that the model is available:

ollama list

7. Create the PAT Model

The repository root contains a file named:

Modelfile

Create the custom PAT model:

ollama create pat -f Modelfile

Verify it:

ollama list

The list should include both the base model and pat:latest.

Test the model directly:

ollama run pat

Ask:

Who are you?

Exit with:

/bye

8. Confirm the Configuration

Open config.py and confirm that the configured Ollama model is:

OLLAMA_MODEL = "pat"

Also confirm the memory database path:

MEMORY_DATABASE = DATA_DIR / "memory.db"

9. Run PAT OS

From the repository root, with the virtual environment active:

python main.py

Example commands:

open notepad

launch calculator

remember my favorite game is Halo

what is my favorite game

who are you

exit

10. Test Individual Components

Test the application launcher:

python -m automation.apps

Test memory:

python -m brain.memory

Test the router:

python -m core.router

Test the task engine:

python -m engines.task_engine

11. Current Limitations

PAT OS v0.1.0 does not yet provide:

Working voice output

Speech-to-text

Wake-word activation

A desktop dashboard

Mobile integration

Computer vision

Autonomous multi-step planning

Folders and placeholder files for future features may already exist in the repository.

12. Troubleshooting

python is not recognized

Reinstall Python and enable the option that adds Python to PATH.

You can also try:

py --version

and create the environment with:

py -m venv .venv

PowerShell blocks virtual-environment activation

Run PowerShell as the current user and enter:

Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

Then try activation again.

Ollama command is not recognized

Close and reopen the terminal after installing Ollama. If needed, restart Windows.

PAT cannot contact Ollama

Verify that Ollama is running:

ollama list

Then test:

ollama run pat

PAT cannot find an application

Open:

automation/apps.py

Add the application name and executable path to APP_PATHS.

The memory database looks unreadable

data/memory.db is a SQLite database, not a text file. Do not edit it directly in VS Code. Use PAT's memory functions or a SQLite database viewer.

13. Updating PAT OS

Before updating:

Commit current work.

Push it to GitHub.

Create a ZIP backup for important milestones.

Then pull new changes:

git pull

Reactivate the virtual environment and update packages:

pip install -r requirements.txt