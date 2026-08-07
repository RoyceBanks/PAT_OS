# Changelog

All notable changes to **PAT OS** will be documented in this file.

PAT OS follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Planned

- Window management
  - Switch between open applications
  - Minimize windows
  - Maximize windows
  - Close windows
  - Show desktop
- Clipboard controls
- Safe file management
- Centralized audio manager
- Improved voice interruption
- Desktop dashboard
- Screen awareness and vision

---

## [0.6.0] - 2026-08-07

### Windows Automation

PAT gained direct, allowlisted Windows system controls.

### Added

#### Audio Controls

- Windows master volume control
- Volume up command
- Volume down command
- Exact volume percentage control
- Increase volume by percentage
- Decrease volume by percentage
- Current volume reporting
- State-aware mute
- State-aware unmute
- Pycaw Windows audio integration

Example commands:

- `Mute the computer.`
- `Unmute the computer.`
- `Turn up the volume.`
- `Set the volume to 40 percent.`
- `Increase the volume by 10 percent.`
- `Lower the volume by 20 percent.`
- `What's the volume at?`

#### Windows Controls

- Computer locking
- Screenshot capture
- Local screenshot storage
- System status monitoring

#### Router

- Added Windows control intents
- Added flexible volume command matching
- Added punctuation normalization
- Improved natural-language command detection
- Prevented supported Windows commands from unnecessarily falling through to the AI

### Improved

- Windows actions only report success when the underlying tool reports success
- Volume command recognition supports multiple natural phrasings
- Safer separation between AI responses and operating-system actions

### Fixed

- Fixed voice commands such as `Turn up the volume`
- Fixed commands with trailing punctuation
- Fixed mute commands incorrectly falling through to general AI
- Replaced toggle-only mute behavior with explicit mute and unmute states
- Updated audio control implementation for the current Pycaw API

---

## [0.5.0] - 2026-08-07

### Live Research and Context

PAT gained live internet research, webpage reading, research memory, and source tracking.

### Added

#### Internet Search

- DuckDuckGo search through DDGS
- Live internet search results
- Search result titles
- Search result URLs
- Search result snippets

#### Webpage Reader

- Safe public webpage fetching
- HTTP and HTTPS validation
- Redirect validation
- Private and local network address blocking
- Download size limits
- Request timeouts
- Content-type validation
- HTML content extraction
- Article and main-content extraction
- Removal of scripts, navigation, forms, and other unnecessary page content

#### Research Engine

- Multi-source research
- Multi-page webpage reading
- Source-grounded local AI responses
- Fresh-information detection
- Automatic routing of current-information questions to live research

Example:

- `What's the latest NVIDIA news?`

#### Research Context

- Temporary research session context
- Follow-up research questions
- Previous topic awareness
- Research source memory
- Source listing
- Opening individual research sources

Example conversation:

- `What's the latest NVIDIA news?`
- `What about AMD?`
- `What sources did you use?`
- `Open the first source.`

#### Speech Corrections

- Added transcription correction layer
- Added correction support for commonly misheard technology names
- Added NVIDIA speech-recognition corrections
- Added corrections for:
  - OpenAI
  - ChatGPT
  - Raspberry Pi
  - Visual Studio Code
  - Firefox
  - YouTube
  - GitHub

### Improved

- Current-information questions now prefer live web research
- Research follow-ups retain the previous topic
- PAT can distinguish normal AI questions from questions requiring current information
- Research results are printed in full while spoken responses remain concise

### Security

- Web content is treated as untrusted input
- Webpage text cannot directly trigger computer automation
- Public URL validation blocks basic access to local and private network services

---

## [0.4.0] - 2026-08-07

### Reminders, Browser, and Reliability

PAT gained persistent reminders, browser controls, and improved system reliability.

### Added

#### Reminders

- SQLite reminder database
- Persistent reminders
- Timers
- Scheduled reminders
- Reminder restoration after restart
- List reminders
- Cancel reminder
- Cancel next reminder
- Cancel all reminders

Example commands:

- `Remind me in 10 minutes to check the oven.`
- `Remind me tomorrow at 8 AM to call John.`
- `What reminders do I have?`
- `Cancel my next reminder.`
- `Cancel all reminders.`

#### Browser

- Default-browser website launching
- Firefox support
- Known website aliases
- DuckDuckGo browser searches

Supported website shortcuts include:

- YouTube
- GitHub
- Gmail
- Google
- Reddit
- Wikipedia
- Spotify
- Amazon
- Facebook
- Instagram
- TikTok

#### Application Commands

- Improved application aliases
- Multi-application commands
- Natural command phrasing

Example commands:

- `Open up Steam.`
- `Open Firefox and Notepad.`
- `Start up Discord.`

#### Session Context

- Added temporary session context
- Added previous research query tracking
- Added previous response tracking

### Improved

- Reminder persistence across PAT restarts
- Browser routing
- Website detection
- Application command parsing
- Multi-application planning

### Fixed

- Fixed website commands being interpreted as application commands
- Fixed `open up` and `start up` phrasing
- Fixed reminder loss after application restart

---

## [0.3.0] - 2026-08-07

### Setup, Health, and Voice Reliability

PAT gained improved installation, testing, and audio reliability.

### Added

#### Setup Utility

- Automated PAT setup script
- Dependency checks
- Directory creation
- Ollama checks
- PAT model checks
- Piper voice setup
- Memory database initialization

#### Health Check

PAT can test:

- Python environment
- Local AI
- Memory
- Microphone
- Voice output

#### System Monitoring

- CPU monitoring
- Memory monitoring
- System status reporting
- psutil integration

#### Speech Output Improvements

- Spoken-response cleanup
- Markdown removal for spoken responses
- URL cleanup
- Maximum spoken-response length
- Maximum spoken sentence count
- Full response remains available in the console

#### Speech Interruption

- Escape key can stop PAT while speaking
- Interruptible audio playback using SoundDevice

### Changed

- Replaced blocking Windows WAV playback with SoundDevice playback
- Improved temporary WAV handling
- Improved text preparation before Piper TTS

### Fixed

- Fixed temporary audio filename errors
- Fixed long AI responses being fully spoken
- Fixed speech playback interruption issues

### Known Limitations

- Full voice barge-in is not yet enabled
- Simultaneous microphone recording and audio playback caused SoundDevice conflicts
- Voice barge-in was intentionally disabled until a centralized audio manager is implemented

---

## [0.2.0] - 2026-08-06

### Voice Interaction

PAT gained its first hands-free voice interface.

### Added

#### Voice Output

- Piper TTS integration
- Local voice synthesis
- Configurable PAT voice
- Local Piper voice models

#### Speech Recognition

- Faster-Whisper integration
- Microphone recording
- Silence-based command detection
- Configurable command timeout
- Configurable silence threshold

#### Wake Phrase

- Voice activation using `Hey Pat`
- Faster-Whisper wake phrase detection
- Separate wake and command recognition models

#### Interaction

- Wake-word mode
- Keyboard command mode
- Spoken PAT responses

### Improved

- AI responses optimized for spoken English
- Reduced Markdown and formatting in voice output

---

## [0.1.0] - 2026-08-06

### Initial Alpha Release

The first working version of PAT OS.

### Added

#### AI

- Local AI integration using Ollama
- Qwen-based local language model
- Custom PAT model
- Custom PAT system prompt
- Conversation support
- PAT identity as Personal AI Technician

#### Core

- Main application structure
- Modular project architecture
- Configuration system
- Intent router
- Command planner

#### Memory

- SQLite memory database
- Long-term memory manager
- Save memories
- Recall memories
- Update memories
- Delete memories

#### Task Engine

- Task creation
- Task queue
- Task execution
- Task history
- Task cancellation

#### Automation

- Safe application launcher
- Allowlisted application control
- Configurable application aliases
- Windows application support

Supported applications included:

- Firefox
- Microsoft Edge
- Discord
- Steam
- Visual Studio Code
- Notepad
- Calculator
- File Explorer
- Task Manager

#### Development

- Python virtual environment support
- Git repository
- Project documentation
- Requirements file
- Modular directory structure

---

# Release Types

PAT OS uses Semantic Versioning:

`MAJOR.MINOR.PATCH`

## Major

Major architectural changes, breaking changes, or stable-generation releases.

Example: `1.0.0`

## Minor

New features or significant new PAT capabilities.

Example: `0.6.0`

## Patch

Bug fixes, reliability improvements, and smaller changes that do not introduce a major new subsystem.

Example: `0.6.1`

---

# Changelog Categories

Future releases may use the following sections:

- Added
- Changed
- Improved
- Fixed
- Removed
- Deprecated
- Security
- Known Limitations