# PAT OS

**PAT** — **Personal AI Technician** — is an open-source, local-first AI computer assistant written in Python.

PAT is designed to be more than a chatbot. It combines local artificial intelligence, voice interaction, persistent memory, live web research, reminders, application control, and Windows automation into a modular personal assistant.

The long-term goal is to build a JARVIS-style assistant that can operate across a computer, phone, smart devices, cameras, and wearable hardware while keeping as much processing local and private as possible.

---

# Current Version

**PAT OS v0.6.0**

**Status:** 🟢 Active Development

**Primary Platform:** Windows

---

# What PAT Can Do

PAT currently supports:

- Local AI conversations using Ollama
- Custom PAT personality/model
- Voice output using Piper TTS
- Speech recognition using Faster-Whisper
- Voice wake phrase detection
- Keyboard interaction mode
- Interrupt speech playback with the Escape key
- Speech transcription correction
- Intent-based command routing
- Application launching
- Multi-application commands
- Website launching
- Web searches
- Live internet research
- Safe webpage reading
- Research follow-up questions
- Research source tracking
- Opening sources from previous research
- Persistent SQLite memory
- Temporary conversation/research context
- Persistent reminders
- Timers
- Scheduled reminders
- Reminder listing and cancellation
- System status monitoring
- Windows volume controls
- Exact volume percentage control
- State-aware mute and unmute
- Computer locking
- Screenshot capture

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
- Autonomous task planning
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

                            │
                      Main Controller
                            │
                ┌───────────┴───────────┐
                │                       │
              Router                Session
                │                    Context
       ┌────────┼────────┐               │
       │        │        │               │
      AI    Automation  Engines        Memory
       │        │        │               │
    Ollama    Windows  Reminders       SQLite
                │       Timers
                │
          Applications
          Browser
          System Controls
                │
                ▼
             Windows


Voice Input
    │
Faster-Whisper
    │
Speech Correction
    │
Wake / Command Detection
    │
Router


Internet Research
    │
DuckDuckGo Search
    │
Safe Webpage Reader
    │
Local AI Analysis
    │
Source Tracking
```

---

# Project Structure

```text
PAT_OS/
│
├── automation/
│   ├── apps.py
│   ├── browser.py
│   ├── system.py
│   └── system_controls.py
│
├── brain/
│   ├── ai.py
│   ├── memory.py
│   └── session_context.py
│
├── core/
│   ├── planner.py
│   └── router.py
│
├── data/
│   ├── memory.db
│   ├── reminders.db
│   ├── history.db
│   └── settings.json
│
├── engines/
│   ├── reminder_engine.py
│   └── task_engine.py
│
├── internet/
│   ├── fetch.py
│   ├── research.py
│   └── search.py
│
├── logs/
├── models/
├── phone/
├── security/
├── skills/
├── sounds/
│
├── speech/
│   ├── corrections.py
│   ├── interrupt.py
│   └── listen.py
│
├── ui/
├── vision/
│
├── voice/
│   └── speak.py
│
├── wakeword/
│   └── detector.py
│
├── config.py
├── health_check.py
├── main.py
├── requirements.txt
├── setup_pat.py
└── README.md
```

Some directories are reserved for future PAT subsystems and may not yet contain production features.

---

# Core Systems

## Local AI

PAT uses **Ollama** to run its language model locally.

The current PAT model is based on **Qwen** with a custom system prompt defining PAT as the user's Personal AI Technician.

PAT's local AI handles conversation and reasoning but does not receive unrestricted control of the computer.

Computer actions are handled through explicitly defined tools and the intent router.

---

## Intent Router

The router determines whether a command should be handled by:

- Local AI
- Memory
- Reminders
- Application automation
- Windows controls
- Website launching
- Web search
- Live research
- Research source handling
- System monitoring

This prevents PAT from simply claiming that it performed an action.

An action is only reported as completed when the corresponding software function actually executes.

---

## Voice System

PAT supports hands-free voice interaction.

Current voice pipeline:

```text
Microphone
    │
Wake Phrase Detection
    │
Faster-Whisper
    │
Speech Corrections
    │
Intent Router
    │
PAT Response
    │
Piper TTS
    │
Speakers
```

PAT's speech can also be interrupted using the **Escape** key.

A more advanced centralized audio manager and full voice barge-in system are planned for a future release.

---

## Memory

PAT contains two types of memory.

### Persistent Memory

Important information can be stored in a local SQLite database and retrieved in later conversations.

### Session Context

PAT temporarily remembers information from the current session, including recent web research topics and sources.

This allows commands such as:

```text
"What about AMD?"

"Tell me more."

"What sources did you use?"

"Open the first source."
```

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

PAT can perform live internet research instead of relying entirely on the knowledge contained in the local AI model.

The research pipeline includes:

```text
User Question
      │
      ▼
DuckDuckGo Search
      │
      ▼
Public URL Validation
      │
      ▼
Safe Webpage Reader
      │
      ▼
Relevant Page Extraction
      │
      ▼
Local AI Analysis
      │
      ▼
PAT Response
```

PAT can read multiple search results, summarize them, remember the research topic, and track the sources used.

Examples:

```text
"What's the latest NVIDIA news?"

"What about AMD?"

"What sources did you use?"

"Open the second source."
```

Webpage content is treated as untrusted information and is not allowed to directly trigger computer automation.

---

# Windows Automation

PAT currently supports several allowlisted Windows actions.

### Applications

PAT can launch approved applications such as:

```text
"Open Firefox."

"Open Steam."

"Open Discord."

"Open Notepad."

"Open Firefox and Notepad."
```

### System Audio

PAT can control Windows master audio.

Examples:

```text
"Mute the computer."

"Unmute the computer."

"Turn up the volume."

"Turn down the volume."

"Set volume to 40 percent."

"Increase volume by 10 percent."

"Lower volume by 20 percent."

"What's the volume at?"
```

### Other Controls

PAT can also:

```text
"Take a screenshot."

"Lock my computer."

"Check system status."
```

Additional desktop and window controls are under development.

---

# Security Model

PAT follows an allowlisted automation design.

The language model does **not** receive unrestricted shell or operating-system access.

Instead:

```text
User Command
      │
      ▼
Intent Router
      │
      ▼
Approved PAT Function
      │
      ▼
Operating System
```

Only actions explicitly implemented by PAT can be executed.

Web content is treated as untrusted and cannot directly issue computer commands.

PAT's webpage reader also performs checks intended to prevent access to local and private network addresses.

---

# Technology Stack

Current and planned technologies include:

| Technology | Purpose |
|---|---|
| Python | Core PAT platform |
| Ollama | Local AI runtime |
| Qwen | Local language model |
| SQLite | Memory and reminders |
| Faster-Whisper | Speech recognition and wake phrase detection |
| Piper | Local text-to-speech |
| PyAudio / SoundDevice | Audio processing |
| PyAutoGUI | Windows automation |
| Pycaw | Windows audio control |
| psutil | System monitoring |
| DDGS | Internet search |
| Requests | Web requests |
| BeautifulSoup | Webpage parsing |
| OpenCV | Planned computer vision |
| Git | Version control |

---

# Development Roadmap

## v0.1 — Core Foundation ✅

- [x] Ollama integration
- [x] Custom PAT model
- [x] Intent router
- [x] SQLite memory
- [x] Task engine
- [x] Application launcher

---

## v0.2 — Voice System ✅

- [x] Piper voice output
- [x] Faster-Whisper speech recognition
- [x] Wake phrase
- [x] Keyboard interaction
- [x] Speech cleanup
- [x] Speech interruption with Escape

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

## v0.6 — Windows Controls 🚧

- [x] System status monitoring
- [x] Volume up/down
- [x] Exact volume percentage
- [x] Volume adjustment by percentage
- [x] Current volume reporting
- [x] State-aware mute
- [x] State-aware unmute
- [x] Screenshot capture
- [x] Lock computer
- [ ] Switch application windows
- [ ] Minimize windows
- [ ] Maximize windows
- [ ] Close windows
- [ ] Show desktop
- [ ] Clipboard controls
- [ ] Safe file management

---

## v0.7 — Desktop Interface

- [ ] Desktop dashboard
- [ ] PAT status display
- [ ] Conversation history
- [ ] System monitoring panel
- [ ] Reminder panel
- [ ] Notification center
- [ ] Settings interface

---

## v0.8 — Vision

- [ ] Screen awareness
- [ ] Screenshot analysis
- [ ] OCR
- [ ] Camera input
- [ ] Object detection
- [ ] Visual task assistance

---

## v0.9 — Connected Devices

- [ ] Android companion
- [ ] Phone notifications
- [ ] SMS integration
- [ ] Calls
- [ ] Remote PAT commands
- [ ] Smart-device integration

---

## v1.0 — PAT OS

Planned initial full release:

- Voice assistant
- Wake phrase
- Local AI
- Long-term memory
- Persistent reminders
- Live internet research
- Computer automation
- Desktop dashboard
- Vision system
- Plugin/skill architecture
- Task planning
- Connected-device support

---

# Planned Future Systems

PAT's longer-term development includes:

### Window Management

Control open desktop applications using natural voice commands.

### Vision

Allow PAT to understand the user's screen and connected cameras.

### Audio Manager

Centralize microphone and speaker streams to support more natural full-duplex conversations and voice interruption.

### Plugin / Skill System

Allow new PAT capabilities to be installed without modifying the core router.

### Phone Companion

Connect PAT to Android for notifications, messaging, remote commands, and mobile voice access.

### Wearable System

Integrate PAT with a future camera-equipped helmet or wearable HUD.

Potential capabilities include:

- Multiple camera feeds
- Microphones
- Speakers
- Displays
- AI vision
- Environmental information
- Navigation
- Voice interaction
- Remote connection to PAT

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
7. New features should be tested independently before being connected to voice control.

---

# Privacy

PAT is intended to be local-first.

Local/private data currently includes:

```text
data/memory.db
data/reminders.db
data/screenshots/
```

These files should be excluded from Git repositories.

Recommended `.gitignore` entries:

```gitignore
# Virtual environment
.venv/

# PAT local databases
data/memory.db
data/reminders.db
data/history.db
data/*.backup

# Screenshots
data/screenshots/

# Local voice models
models/voices/*.onnx
models/voices/*.onnx.json

# Python cache
__pycache__/
*.py[cod]
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