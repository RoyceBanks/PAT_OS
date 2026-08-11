# PAT OS

**PAT — Personal AI Technician** is an open-source, local-first AI computer assistant written in Python.

PAT is designed to be more than a chatbot. It combines local artificial intelligence, voice interaction, persistent memory, live web research, reminders, file and process tools, application control, and Windows automation into a modular personal assistant.

The long-term goal is to build a JARVIS-style assistant that can operate across a computer, phone, smart devices, cameras, and wearable hardware while keeping as much processing local and private as practical.

---

# Current Version

**Stable:** PAT OS v0.8.0  
**In Development:** PAT OS v0.9 — Object-Aware Action Context  
**Status:** Active Development  
**Primary Platform:** Windows

PAT v0.8 completed the conversation engine and centralized audio work. PAT v0.9 is focused on making conversational references such as **“it,” “that,” “the second one,”** and **“open it again”** resolve to the correct object across different PAT tools.

---

# Current Capabilities

PAT currently supports:

- Local AI conversations using Ollama
- Custom PAT personality/model
- Centralized audio stream management
- Voice output using Piper TTS
- Speech recognition using Faster-Whisper
- Wake phrase detection
- Voice and keyboard interaction
- Speech transcription correction
- Conversation follow-up listening
- Voice interruption / barge-in support
- Intent-based command routing
- Application launching
- Multi-application commands
- Window switching, minimizing, maximizing, and closing
- Website launching
- Web searches
- Live internet research
- Safe webpage reading
- Research follow-up questions
- Research source tracking
- Opening and summarizing previous research sources
- Persistent SQLite memory
- Session conversation context
- Object-aware ActiveTarget context
- Persistent reminders
- Timers and scheduled reminders
- Reminder listing and cancellation
- System status monitoring
- Process monitoring
- Approved process close actions
- Windows volume controls
- Exact volume percentage control
- State-aware mute and unmute
- Clipboard tools
- File search
- File open and folder reveal
- File copy, move, and rename
- Safe file deletion through the Windows Recycle Bin
- Computer locking
- Screenshot capture
- Confirmation protection for destructive actions
- Automated system health testing

PAT's current health suite checks **13 systems**:

1. Python
2. AI
3. Memory
4. Microphone
5. Voice
6. Reminders
7. Internet / Research
8. Windows Audio
9. Window Management
10. Clipboard
11. File Manager
12. Process Monitoring
13. Confirmation Safety

---

# v0.9 Development Focus

PAT v0.9 introduces a unified conversational object called **ActiveTarget**.

Instead of maintaining unrelated pronoun logic for every feature, PAT can remember the object currently being discussed.

Current ActiveTarget types include:

```text
research_source
file
process
application
```

Working examples:

```text
Search for Python tutorials.
Open the second one.
Tell me more about it.
```

```text
Find my resume.
Open the second one.
Copy that to Desktop.
```

```text
Show top memory processes.
Tell me about the second one.
What's its PID?
Close it.
```

```text
Open Notepad.
Minimize it.
Maximize it.
What's its PID?
Close it.
Open it again.
```

### Completed in v0.9 so far

- [x] Unified `ActiveTarget` object
- [x] Research-source ActiveTarget support
- [x] File ActiveTarget support
- [x] Process ActiveTarget support
- [x] Application/window ActiveTarget support
- [x] Natural numbered-result references
- [x] Parser priority for contextual references
- [x] Safe file deletion through Recycle Bin
- [x] Approved-process close protection
- [x] Confirmation safety preserved
- [x] 13/13 health suite after context migration

### Still in progress

- [ ] Website/browser ActiveTarget support
- [ ] Centralized generic object-reference resolver
- [ ] Removal of remaining legacy context fields where safe
- [ ] Additional regression coverage
- [ ] Final v0.9 version bump and release checkpoint

---

# Vision

PAT is inspired by fictional assistants such as JARVIS, but is being built using real, accessible, primarily open-source software.

PAT is designed around several long-term goals:

- Natural voice conversations
- Local AI reasoning
- Computer automation
- Long-term memory
- Live internet research
- Computer vision
- Safe autonomous task planning
- Phone integration
- Smart-home integration
- Wearable hardware integration
- AI-assisted camera systems
- HUD interfaces

PAT should eventually be able to receive a natural-language request, determine what tools are required, safely perform the task, and report the result.

---

# Architecture

PAT uses a modular architecture so individual systems can be upgraded or replaced without rebuilding the entire project.

```text
                         PAT OS
                           |
                    Main Controller
                           |
                  +--------+--------+
                  |                 |
                Router        Session Context
                  |                 |
        +---------+---------+       |
        |         |         |       |
       AI     Automation   Engines   |
        |         |         |       |
     Ollama    Windows   Reminders   |
                  |       Timers     |
                  |                 |
        +---------+---------+       |
        |         |         |       |
   Applications  Files   Processes  |
        |         |         |       |
      Windows   Clipboard  Windows  |
                           |
                     ActiveTarget
```

Voice pipeline:

```text
Microphone
   |
Audio Manager
   |
Wake / Command Detection
   |
Faster-Whisper
   |
Speech Corrections
   |
Intent Router
   |
PAT Response
   |
Piper TTS
   |
Audio Manager
   |
Speakers
```

Research pipeline:

```text
User Question
   |
Internet Search
   |
Public URL Validation
   |
Safe Webpage Reader
   |
Relevant Page Extraction
   |
Local AI Analysis
   |
Source Tracking
   |
PAT Response
```

---

# Project Structure

```text
PAT_OS/
|
+-- audio/
|   +-- __init__.py
|   +-- audio_manager.py
|
+-- automation/
|   +-- apps.py
|   +-- browser.py
|   +-- clipboard.py
|   +-- file_manager.py
|   +-- process_controls.py
|   +-- process_monitor.py
|   +-- system.py
|   +-- system_controls.py
|   +-- window_controls.py
|
+-- brain/
|   +-- ai.py
|   +-- memory.py
|   +-- session_context.py
|
+-- core/
|   +-- planner.py
|   +-- router.py
|
+-- data/
|
+-- engines/
|   +-- reminder_engine.py
|   +-- task_engine.py
|
+-- internet/
|   +-- fetch.py
|   +-- research.py
|   +-- search.py
|
+-- logs/
+-- models/
+-- phone/
+-- security/
+-- skills/
+-- sounds/
|
+-- speech/
|   +-- corrections.py
|   +-- listen.py
|
+-- ui/
+-- vision/
|
+-- voice/
|   +-- speak.py
|
+-- wakeword/
|   +-- detector.py
|
+-- config.py
+-- health_check.py
+-- main.py
+-- requirements.txt
+-- setup_pat.py
+-- README.md
```

Some directories are reserved for future PAT subsystems and may not yet contain production features.

---

# Core Systems

## Local AI

PAT uses **Ollama** to run its language model locally.

The current PAT model is based on **Qwen** with a custom system prompt defining PAT as the user's Personal AI Technician.

The language model handles conversation and reasoning, but it does not receive unrestricted control of the computer.

Computer actions are executed through explicit PAT tools and the intent router.

---

## Intent Router

The router determines whether a command should be handled by:

- Local AI
- Memory
- Reminders
- Application automation
- Window management
- File tools
- Clipboard tools
- Process tools
- Website launching
- Web search
- Live research
- Research source handling
- System monitoring
- Confirmation safety

PAT should never report that an action succeeded unless the corresponding tool reports success.

---

## Audio Manager

PAT v0.7 introduced a centralized audio manager.

The audio manager owns PAT's microphone and speaker streams and coordinates:

- Listening state
- Speaking state
- Input buffering
- Output playback
- Cancellation
- Wake detection
- Voice interruption / barge-in
- Speaker-reference buffering for future echo-cancellation work

Centralizing audio ownership avoids multiple PAT components fighting over the microphone or speakers.

---

## Voice System

PAT supports hands-free voice interaction.

Current voice pipeline:

```text
Microphone
   |
Audio Manager
   |
Wake Phrase Detection
   |
Faster-Whisper
   |
Speech Corrections
   |
Intent Router
   |
PAT Response
   |
Piper TTS
   |
Speakers
```

PAT can continue listening briefly after a response so natural follow-up commands can be spoken without repeating the wake phrase every time.

---

## Conversation Context

PAT v0.8 added a stronger conversation engine with temporary session context and bounded local-AI conversation history.

PAT can understand follow-up requests such as:

```text
"Tell me more about it."
"Open the second one."
"What's its PID?"
"Close it."
"Open it again."
```

PAT v0.9 is consolidating those references into the unified `ActiveTarget` system.

---

## Memory

PAT contains persistent and temporary memory systems.

### Persistent Memory

Important information can be stored in a local SQLite database and retrieved in later conversations.

### Session Context

PAT temporarily remembers the current conversation, recent research, result selections, pending confirmations, and the active conversational object.

Session context is temporary and is cleared when appropriate.

---

## Reminders and Timers

PAT supports persistent reminders stored in SQLite.

Examples:

```text
"Remind me in 10 minutes to check the oven."
"Remind me tomorrow at 8 AM to call John."
"What reminders do I have?"
"Cancel my next reminder."
"Cancel all reminders."
```

Persistent reminders survive PAT restarts.

---

# Internet Research

PAT can perform live internet research instead of relying entirely on the local model's stored knowledge.

PAT can:

- Search the web
- Read public webpages
- Reject local/private network targets
- Extract useful page text
- Treat webpage content as untrusted
- Summarize individual sources
- Track numbered research sources
- Open previous sources
- Continue discussing a selected source

Examples:

```text
"Search for Python tutorials."
"Open the second result."
"Tell me more about it."
"Tell me more about the third one."
"Summarize it."
```

Webpage content is treated as untrusted information and cannot directly trigger computer automation.

---

# Windows Automation

PAT uses allowlisted Windows automation rather than unrestricted shell access.

## Applications and Windows

Examples:

```text
"Open Firefox."
"Open Steam."
"Open Notepad."
"Minimize it."
"Maximize it."
"Close it."
"Open it again."
```

PAT can also switch between approved application windows.

---

## Process Monitoring

PAT can inspect running processes and report details such as memory use and process IDs.

Examples:

```text
"Show top memory processes."
"Show top CPU processes."
"Tell me about the second one."
"What's its PID?"
"Close it."
```

Process closing is restricted to approved applications. PAT will refuse to terminate unapproved background or system processes through this route.

---

## File Management

PAT supports contextual file workflows.

Examples:

```text
"Find resume."
"Open the second one."
"Copy that to Desktop."
"Move it to Documents."
"Rename it."
"Delete it."
```

Deletion uses the Windows Recycle Bin through `send2trash`.

Destructive file actions require confirmation.

---

## Clipboard

PAT includes clipboard read/write automation for approved workflows.

---

## System Audio

PAT can control Windows master audio.

Examples:

```text
"Mute the computer."
"Unmute the computer."
"Turn up the volume."
"Turn down the volume."
"Set volume to 40 percent."
"Increase volume by 10 percent."
"What's the volume at?"
```

---

## Other Controls

PAT can also:

```text
"Take a screenshot."
"Lock my computer."
"Check system status."
```

---

# Security Model

PAT follows an allowlisted automation design.

The language model does **not** receive unrestricted shell or operating-system access.

```text
User Command
   |
Intent Router
   |
Approved PAT Function
   |
Safety / Confirmation Layer
   |
Operating System
```

Important safety rules:

- Only explicitly implemented actions may execute.
- Process closing is limited to approved applications.
- Destructive actions retain confirmation requirements.
- File deletion goes to the Windows Recycle Bin.
- Web content is treated as untrusted.
- Web content cannot directly issue computer commands.
- Local/private network targets are blocked by the webpage reader.
- PAT should never claim success unless the tool reports success.

---

# Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core PAT platform |
| Ollama | Local AI runtime |
| Qwen | Local language model |
| SQLite | Memory and reminders |
| Faster-Whisper | Speech recognition |
| Piper | Local text-to-speech |
| SoundDevice | Audio input/output |
| NumPy | Audio/data processing |
| PyAutoGUI | Windows automation |
| Pycaw | Windows audio control |
| psutil | Process/system monitoring |
| PyGetWindow | Window management |
| Pyperclip | Clipboard automation |
| send2trash | Safe Recycle Bin deletion |
| DDGS | Internet search |
| Requests | Web requests |
| BeautifulSoup | Webpage parsing |
| Pillow | Image utilities |
| OpenCV | Future computer vision |
| Git | Version control |
| pytest | Automated testing |

---

# Development Roadmap

## v0.1 — Core Foundation ✅

- [x] Ollama integration
- [x] Custom PAT model
- [x] Intent router
- [x] SQLite memory
- [x] Task engine foundation
- [x] Application launcher

---

## v0.2 — Voice System ✅

- [x] Piper voice output
- [x] Faster-Whisper speech recognition
- [x] Wake phrase
- [x] Keyboard interaction
- [x] Speech cleanup
- [x] Voice command loop

---

## v0.3 — Persistence and Reliability ✅

- [x] Automated setup
- [x] Health checks
- [x] Persistent reminders
- [x] Timers
- [x] Scheduled reminders
- [x] Reminder restoration after restart
- [x] Speech transcription corrections

---

## v0.4 — Browser and Internet ✅

- [x] Website launcher
- [x] Browser search
- [x] Live internet search
- [x] Safe webpage reader
- [x] Multi-page research
- [x] Fresh-information detection

---

## v0.5 — Research Context ✅

- [x] Research follow-up questions
- [x] Session context
- [x] Research source tracking
- [x] List research sources
- [x] Open previous research sources
- [x] Source-grounded AI responses

---

## v0.6 — Windows Controls ✅

- [x] System status monitoring
- [x] Volume controls
- [x] Screenshot capture
- [x] Computer locking
- [x] Window switching
- [x] Window minimize/maximize
- [x] Window close
- [x] Clipboard controls
- [x] File management
- [x] Process monitoring
- [x] Confirmation safety

---

## v0.7 — Audio Engine ✅

- [x] Centralized audio manager
- [x] Persistent microphone stream
- [x] Persistent output stream
- [x] Input buffering
- [x] Speaking/listening state coordination
- [x] Playback cancellation
- [x] Voice interruption / barge-in
- [x] Speaker-reference buffer for future AEC work

---

## v0.8 — Conversation Engine ✅

- [x] Follow-up conversation window
- [x] Quiet follow-up listening
- [x] Session conversation context
- [x] Contextual process references
- [x] Contextual application/window references
- [x] Context-aware research handling
- [x] Bounded local-AI conversation history
- [x] Conversation timeout cleanup

---

## v0.9 — Object-Aware Actions 🚧

- [x] Unified `ActiveTarget` foundation
- [x] Research-source target
- [x] File target
- [x] Process target
- [x] Application target
- [x] Natural numbered-result selection
- [x] Contextual parser priority
- [ ] Website/browser target
- [ ] Centralized generic reference resolver
- [ ] Legacy context cleanup
- [ ] Final regression pass
- [ ] v0.9 release checkpoint

---

## v1.0 — PAT OS

Planned initial full release goals:

- Stable voice assistant
- Wake phrase
- Local AI
- Long-term memory
- Persistent reminders
- Live internet research
- Safe computer automation
- Object-aware conversation context
- Plugin/skill architecture
- Task planning
- Extensible device interfaces

---

# Experimental Development

## FORGE Code Agent

FORGE is an experimental coding-agent subsystem being developed separately from PAT's stable v0.8 feature set.

The goal is to let PAT delegate scoped coding tasks to a specialized agent while maintaining strict file boundaries and safety rules.

Current experimental goals include:

- User-defined file scope
- Implementation-plan generation
- Scope validation
- Rejecting modifications outside approved files
- Safe proposal/execution stages
- Local Ollama integration
- Automated tests

FORGE should not be considered part of a stable PAT release until its workflow and regression tests are complete.

---

# Planned Future Systems

## Desktop Interface

A desktop dashboard for:

- PAT status
- Conversation history
- System monitoring
- Reminders
- Notifications
- Settings

## Vision

Future vision work may include:

- Screen awareness
- Screenshot analysis
- Camera input
- Object detection
- Visual task assistance

## Plugin / Skill System

Allow new PAT capabilities to be installed without modifying the core router.

## Phone Companion

Connect PAT to a phone for notifications, messaging, remote commands, and mobile voice access.

## Wearable System

Integrate PAT with future camera-equipped wearable hardware or a HUD.

Potential capabilities include:

- Multiple camera feeds
- Microphones
- Speakers
- Displays
- AI vision
- Environmental information
- Navigation
- Voice interaction
- Remote PAT connection

---

# Design Philosophy

PAT should be:

**Local-first**  
Use local models and processing whenever practical.

**Private**  
Keep personal memory and assistant data under the user's control.

**Modular**  
Individual systems should be replaceable without rewriting PAT.

**Action-oriented**  
PAT should perform real actions rather than pretend an action occurred.

**Safe**  
Computer automation should use explicit, allowlisted capabilities.

**Expandable**  
New devices, skills, models, and interfaces should be easy to add.

**Understandable**  
PAT should remain a project that can be inspected, modified, and maintained by its owner.

---

# Development Principles

PAT follows a few important rules:

1. The AI model does not receive unrestricted computer access.
2. Computer actions must go through approved tools.
3. PAT should never claim an action succeeded unless the tool reports success.
4. Internet content is treated as untrusted.
5. Local processing is preferred when practical.
6. Personal databases and screenshots should not be committed to Git.
7. Destructive actions should preserve confirmation requirements.
8. New features should be tested independently before being connected to voice control.
9. Stable milestones should be checkpointed in Git before major architectural changes.

---

# Privacy

PAT is intended to be local-first.

Local/private data may include:

```text
data/memory.db
data/reminders.db
data/history.db
data/screenshots/
```

These files should not be committed to public repositories.

Recommended `.gitignore` entries:

```gitignore
# Virtual environments
.venv/
.venv_uv_backup/

# Python generated files
__pycache__/
*.pyc

# PAT runtime data
data/memory.db
data/reminders.db
data/history.db
data/*.backup

# Screenshots
data/screenshots/

# Local voice models
models/voices/*.onnx
models/voices/*.onnx.json
```

---

# Running PAT

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Start PAT:

```powershell
python main.py
```

Run the setup utility:

```powershell
python setup_pat.py
```

Run PAT's health check:

```powershell
python health_check.py
```

Expected current health result:

```text
Systems passed: 13/13
All tested PAT systems are operational.
```

---

# Development Workflow

PAT development uses small, testable changes.

Recommended workflow:

```text
Make one focused change
        |
Compile
        |
Run direct test
        |
Run health_check.py
        |
Run live voice test when relevant
        |
Commit stable checkpoint
```

Before committing:

```powershell
git status --short
```

Avoid staging unrelated experimental work with:

```text
git add .
```

when multiple features are being developed at the same time.

---

# Contributing

PAT OS is under active development.

The project is intended to remain modular so new skills, automation modules, AI models, hardware interfaces, and integrations can be added over time.

---

# Author

**Project:** PAT OS  
**Assistant:** PAT  
**Meaning:** Personal AI Technician

PAT OS is being developed as a long-term open-source personal AI operating assistant.
