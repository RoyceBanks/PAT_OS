# PAT OS

**PAT — Personal AI Technician** is an open-source, local-first AI computer assistant written in Python.

PAT is designed to be more than a chatbot. It combines local artificial intelligence, hands-free voice interaction, persistent memory, live web research, reminders, file and process tools, application and browser control, Windows automation, object-aware conversational context, a real-time desktop HUD, and experimental specialist agents.

The long-term goal is to build a JARVIS-style personal assistant that can operate across a computer, phone, smart devices, cameras, and wearable hardware while keeping as much processing local and private as practical.

---

# Current Version

**Stable:** PAT OS v0.8.0  
**In Development:** PAT OS v0.9 — Object-Aware Actions, Visual Interface, and Agent Integration  
**Status:** Active Development  
**Primary Platform:** Windows 11

PAT v0.8 completed the conversation engine and centralized audio work.

PAT v0.9 has stabilized the unified `ActiveTarget` context layer across research sources, files, processes, applications, and websites. Current v0.9 development is expanding the desktop visual interface and integrating the experimental FORGE/SENTINEL coding-agent workflow.

The version has **not** been bumped to v0.9.0 yet.

---

# Current Capabilities

PAT currently supports:

- Local AI conversations using Ollama
- Custom PAT personality/model
- Hands-free startup directly into wake mode
- Wake phrase detection using **"Hey Pat"**
- Centralized audio stream management
- Voice output using Piper TTS
- Speech recognition using Faster-Whisper
- Speech transcription correction
- Conversation follow-up listening
- Voice interruption / barge-in support
- Intent-based command routing
- Application launching
- Multi-application commands
- Window switching, minimizing, maximizing, and closing
- Website launching in Firefox
- Safe website-tab switching and closing
- Web searches and live internet research
- Safe webpage reading and research-source tracking
- Persistent SQLite memory
- Session conversation context
- Unified object-aware `ActiveTarget` context
- Persistent reminders and timers
- System and process monitoring
- Approved process close actions
- Windows volume controls
- Clipboard tools
- File search, open, reveal, copy, move, and rename
- Safe file deletion through the Windows Recycle Bin
- Computer locking and screenshot capture
- Confirmation protection for destructive actions
- Automated system health testing
- PySide6 desktop HUD
- HUD states for idle, listening, thinking, speaking, and confirmation
- Live user-command, PAT-response, and ActiveTarget display
- Process-safe UI bridge
- Experimental real-audio voice visualization
- Experimental FORGE coding-agent delegation
- SENTINEL pre-review/post-review workflow
- Explicit FORGE approve/deny commands
- Immediate spoken acknowledgment when a task is handed to FORGE
- Short spoken FORGE/SENTINEL summaries instead of reading full reports aloud

---

# Health Status

PAT's health suite checks **13 systems**:

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

Last confirmed stable baseline:

```text
Systems passed: 13/13
All tested PAT systems are operational.
```

Because the UI and FORGE integration are still under active development, run `health_check.py` before creating a release checkpoint.

---

# v0.9 Development Focus

## Unified ActiveTarget

PAT v0.9 introduces a unified conversational object called **ActiveTarget**.

Current ActiveTarget types:

```text
research_source
file
process
application
website
```

Examples:

```text
Search for Python tutorials.
Open the second one.
Tell me more about it.
Open it.
```

```text
Find my resume.
Open the second one.
Open its folder.
Delete it.
```

```text
Show top memory processes.
Tell me about the second one.
What's its PID?
Close it.
Open it.
```

```text
Open Notepad.
Minimize it.
Maximize it.
Close it.
Open it.
```

```text
Open YouTube.
Switch to it.
Close it.
Open it.
```

### ActiveTarget work completed

- [x] Unified `ActiveTarget` object
- [x] Research-source target
- [x] File target
- [x] Process target
- [x] Application target
- [x] Website target
- [x] Natural numbered-result references
- [x] Contextual parser priority
- [x] Contextual `open it`
- [x] Contextual file-folder references
- [x] Contextual website-tab switching
- [x] Safe website-tab closing with URL verification
- [x] Legacy window/process/file/research context cleanup
- [x] ActiveTarget parser regression coverage
- [x] Confirmation safety preserved

### Still in progress

- [ ] Final v0.9 release regression pass
- [ ] Final documentation cleanup
- [ ] Final v0.9 version bump and release checkpoint
- [ ] Stabilize the new visual interface
- [ ] Stabilize FORGE/SENTINEL voice and HUD approval flow

---

# Visual Interface

PAT now has a modern **PySide6** HUD with an original futuristic design.

Current HUD features:

- Frameless desktop window
- Glass-style translucent panels
- Layered gradients, shadows, highlights, and simulated 3D depth
- Animated central PAT core
- User-command display
- PAT-response display
- ActiveTarget display
- System-status tiles
- Draggable title bar
- Window controls
- Real-time state transitions

Current visual states:

```text
IDLE
LISTENING
THINKING
SPEAKING
AWAITING CONFIRMATION
```

Typical live flow:

```text
Waiting for "Hey Pat"
        |
       IDLE
        |
Wake phrase detected
        |
PAT says "Yes?"
        |
     SPEAKING
        |
     LISTENING
        |
User command
        |
     THINKING
        |
PAT response
        |
     SPEAKING
        |
Follow-up listening / IDLE
```

The PySide6 GUI runs in its own process through a process-safe bridge so Qt can own its GUI thread without interfering with PAT's voice, router, or audio loops.

Current UI modules:

```text
ui/
+-- __init__.py
+-- pat_window_qt.py
+-- pat_ui_bridge.py
+-- pat_audio_visualizer.py
```

`pat_audio_visualizer.py` reads PAT's existing speaker-reference buffer from `AudioManager`; it does not open another audio stream.

---

# FORGE and SENTINEL

PAT includes an experimental specialist-agent workflow for coding tasks.

**FORGE** prepares or performs scoped coding work.  
**SENTINEL** reviews FORGE's proposed or completed changes for correctness, safety, scope, and quality.

Intended controlled workflow:

```text
User
 |
"Have Forge make..."
 |
PAT acknowledges immediately
 |
FORGE prepares plan
 |
SENTINEL pre-review
 |
If needed: FORGE revises
 |
SENTINEL reviews again
 |
PAT gives a very short summary
 |
USER APPROVE / DENY
 |
Controlled write
 |
Validation
 |
SENTINEL post-review
 |
Commit result or rollback
```

PAT immediately acknowledges a new FORGE job so the user knows delegation succeeded:

```text
Got it. I sent that to Forge.
I'll let you know when Sentinel finishes reviewing it.
```

After SENTINEL completes pre-review, PAT should speak only a concise summary instead of reading the full report:

```text
Forge prepared a small command-line calculator.
Sentinel approved it with notes.
Say approve Forge changes or deny Forge changes.
```

Explicit approval commands:

```text
approve forge changes
deny forge changes
```

A generic `"yes"` should not substitute for explicit FORGE approval.

Detailed FORGE output, diffs, task IDs, validation results, and SENTINEL reviews remain available in the console/logs.

## FORGE Safety Principles

- Existing-project edits require an approval gate.
- SENTINEL must approve the proposal before the user is asked to approve it.
- Approved plans should remain locked between review and execution.
- Validation runs after controlled writes.
- SENTINEL performs post-apply review.
- Failed post-apply review can trigger rollback.
- PAT should clearly report when no files were modified.
- FORGE approvals remain explicit.
- Experimental FORGE files should not be mixed into unrelated stable commits.

The HUD integration for the final FORGE approval state is still being refined.

---

# Architecture

```text
                               PAT OS
                                 |
                           Main Controller
                                 |
          +----------------------+----------------------+
          |                      |                      |
        Router             Session Context             UI
          |                      |                      |
  +-------+--------+       ActiveTarget          PySide6 HUD
  |       |        |                               |
 AI   Automation  Engines                         Bridge
  |       |        |                               |
Ollama  Windows  Reminders                  Voice Visualizer
          |
    +-----+------+----------+
    |            |          |
 Applications   Files    Processes
    |
 Browser / Websites

                    Experimental Agent Layer

                           PAT Router
                               |
                             FORGE
                               |
                         SENTINEL Review
                               |
                        User Approve/Deny
                               |
                     Controlled Transaction
```

Voice pipeline:

```text
Microphone
   |
Audio Manager
   |
Wake Detection
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
   +--------------------+
   |                    |
Speakers         Speaker Reference
                         |
                 HUD Voice Visualizer
```

---

# Project Structure

```text
PAT_OS/
|
+-- agents/
|   +-- forge/
|   +-- sentinel/
|   +-- manager.py
|   +-- approval.py
|
+-- audio/
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
+-- engines/
+-- forge_projects/
+-- internet/
+-- logs/
+-- models/
+-- speech/
|   +-- corrections.py
|   +-- listen.py
|
+-- ui/
|   +-- __init__.py
|   +-- pat_window_qt.py
|   +-- pat_ui_bridge.py
|   +-- pat_audio_visualizer.py
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

---

# Core Systems

## Local AI

PAT uses **Ollama** to run its language model locally. The current PAT model is based on **Qwen** with a custom system prompt.

The language model handles conversation and reasoning, but it does not receive unrestricted computer control. Computer actions go through explicit PAT tools and routing logic.

## Audio Manager

PAT's centralized audio manager owns microphone and speaker streams and coordinates listening, speaking, buffering, cancellation, wake detection, barge-in, and speaker-reference buffering.

## Voice System

PAT launches directly into hands-free wake mode when `main.py` starts. There is no startup prompt requiring Enter to enable wake mode.

```text
python main.py
   |
Systems online
   |
Microphone starts
   |
Waiting for "Hey Pat"
```

## Conversation Context

PAT v0.8 added temporary session context and bounded local-AI conversation history. PAT v0.9 migrated action-oriented conversational references onto `ActiveTarget`.

## Memory

PAT contains persistent SQLite memory plus temporary session context for recent turns, result lists, research state, pending confirmations, and `ActiveTarget`.

## Reminders and Timers

PAT supports persistent reminders and timers that survive PAT restarts.

---

# Windows Automation

PAT uses allowlisted Windows automation rather than unrestricted shell access.

## Applications and Windows

```text
Open Firefox.
Open Steam.
Open Notepad.
Minimize it.
Maximize it.
Close it.
Open it.
```

## Websites and Browser Tabs

PAT distinguishes websites from Windows applications.

```text
Open YouTube.
Switch to it.
Go to it.
Close it.
Open it.
```

Website-tab closing verifies the active Firefox URL before sending `Ctrl+W`.

## Process Monitoring

PAT can inspect running processes and close only approved applications through the protected process route.

## File Management

PAT supports contextual file workflows and uses the Windows Recycle Bin through `send2trash` for deletion. Destructive file actions retain confirmation requirements.

---

# Security Model

```text
User Command
   |
Intent Router
   |
Approved PAT Function / Agent Workflow
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
- Local/private network targets are blocked by the webpage reader.
- Browser-tab closing verifies the active URL.
- FORGE approvals must remain explicit.
- PAT should never claim success unless the responsible tool or workflow reports success.

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
| PySide6 | Desktop HUD |
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

## v0.2 — Voice System ✅

- [x] Piper voice output
- [x] Faster-Whisper speech recognition
- [x] Wake phrase
- [x] Speech cleanup
- [x] Voice command loop

## v0.3 — Persistence and Reliability ✅

- [x] Automated setup
- [x] Health checks
- [x] Persistent reminders
- [x] Timers
- [x] Scheduled reminders
- [x] Speech transcription corrections

## v0.4 — Browser and Internet ✅

- [x] Website launcher
- [x] Browser search
- [x] Live internet search
- [x] Safe webpage reader
- [x] Multi-page research

## v0.5 — Research Context ✅

- [x] Research follow-up questions
- [x] Session context
- [x] Research source tracking
- [x] Open previous research sources
- [x] Source-grounded AI responses

## v0.6 — Windows Controls ✅

- [x] System status monitoring
- [x] Volume controls
- [x] Screenshot capture
- [x] Computer locking
- [x] Window management
- [x] Clipboard controls
- [x] File management
- [x] Process monitoring
- [x] Confirmation safety

## v0.7 — Audio Engine ✅

- [x] Centralized audio manager
- [x] Persistent microphone/output management
- [x] Input buffering
- [x] Speaking/listening coordination
- [x] Playback cancellation
- [x] Voice interruption / barge-in
- [x] Speaker-reference buffer

## v0.8 — Conversation Engine ✅

- [x] Follow-up conversation window
- [x] Quiet follow-up listening
- [x] Session conversation context
- [x] Context-aware process/application/research handling
- [x] Bounded local-AI conversation history
- [x] Conversation timeout cleanup

## v0.9 — Object-Aware Actions + Interface 🚧

### Context

- [x] Unified `ActiveTarget`
- [x] Research, file, process, application, and website targets
- [x] Contextual reopen
- [x] Website-tab context
- [x] File-folder context
- [x] Legacy context cleanup
- [x] Parser regression coverage

### Interface

- [x] PySide6 HUD foundation
- [x] Process-safe GUI bridge
- [x] Live user-command display
- [x] Live PAT-response display
- [x] Live ActiveTarget display
- [x] IDLE / LISTENING / THINKING / SPEAKING states
- [x] AWAITING CONFIRMATION visual state
- [x] Automatic wake-mode startup
- [ ] Final HUD state-synchronization regression
- [ ] Final real-audio visualization regression
- [ ] UI settings/configuration layer

### FORGE / SENTINEL

- [x] FORGE task routing
- [x] SENTINEL review foundation
- [x] Existing-project proposal review
- [x] Explicit Forge approve/deny commands
- [x] Immediate spoken Forge handoff acknowledgment
- [x] Brief spoken Forge/Sentinel summary
- [ ] Finalize generated-project approval gating
- [ ] Finalize HUD confirmation-state behavior
- [ ] Full FORGE/SENTINEL voice acceptance test
- [ ] Separate experimental/stable Git cleanup

### Release

- [ ] Run full health suite
- [ ] Run full live voice regression
- [ ] Update remaining old docs
- [ ] Final v0.9 version bump
- [ ] Create v0.9 release checkpoint

---

# Design Philosophy

PAT should be **local-first, private, modular, action-oriented, safe, expandable, and understandable**.

Development principles:

1. The AI model does not receive unrestricted computer access.
2. Computer actions must go through approved tools.
3. PAT should never claim success unless the tool reports success.
4. Internet content is treated as untrusted.
5. Local processing is preferred when practical.
6. Personal databases and screenshots should not be committed to Git.
7. Destructive actions should preserve confirmation requirements.
8. FORGE approvals should remain explicit.
9. New features should be tested independently before being connected to voice control.
10. Stable milestones should be checkpointed in Git before major architectural changes.

---

# Privacy

Local/private data may include:

```text
data/memory.db
data/reminders.db
data/history.db
data/screenshots/
```

These files should not be committed to public repositories.

---

# Running PAT

Activate the environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Start PAT:

```powershell
python main.py
```

PAT starts directly in hands-free wake mode.

Run health checks:

```powershell
python health_check.py
```

Run setup checks:

```powershell
python setup_pat.py
```

---

# Development Workflow

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

Avoid `git add .` when unrelated experimental work exists. Stage only the files intentionally included in the checkpoint.

---

# Documentation Status

The main README reflects the current PAT v0.8/v0.9 development state.

Some older documents may still reference early PAT versions and should be refreshed before v0.9, especially:

```text
docs/user_guide.md
docs/installation.md
docs/api.md
```

---

# Author

**Project:** PAT OS  
**Assistant:** PAT  
**Meaning:** Personal AI Technician

PAT OS is being developed as a long-term open-source personal AI operating assistant.
