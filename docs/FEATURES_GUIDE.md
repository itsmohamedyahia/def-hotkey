# def (Hotkey Dictionary) — Features & Guardrails Guide

> [!IMPORTANT]
> **ATTENTION ALL AI AGENTS & DEVELOPERS:**
> This guide is the source of truth for the features and architectural constraints of **def**. When you are asked to make changes, add features, or refactor code:
> 1. **DO NOT** break existing features.
> 2. **DO NOT** add unsolicited settings, buttons, or menus that clutter the distraction-free design.
> 3. **DO NOT** deviate from the specific Happy and Bad paths defined below.
> 4. **DO NOT** block the Tkinter main event loop with synchronous scraping, download, or audio playback operations.

---

## 🛠️ System-Wide Architecture & Guardrails

These core system behaviors must not be modified or broken under any circumstances.

### 1. Single Instance Enforcement
- **Mechanics:** The app uses a Windows-named mutex (`def_dictionary_mutex`) to ensure only one instance is active. If a new instance is launched (e.g. by the user or an installer), it exits immediately.
- **Code Reference:** See [def.py:L1276-1285](file:///s:/MEGA/Scripts-Code/%23HEAVILY_USED/def/def.py#L1276-1285).
- **Happy Path:** Only one instance runs. Subsequent launches fail silently.
- **Bad Path:** Spawning multiple instances or windows, resulting in hotkey registration conflicts or database lock exceptions.

### 2. Window Lifecycle (Hide Instead of Close)
- **Mechanics:** The window closing protocols (`WM_DELETE_WINDOW` and the `Escape` key) do not close/terminate the process. Instead, they call `withdraw()` to hide the windows, keeping the application running in the background. The only way to exit the program is via the **System Tray Icon -> Exit** option.
- **Code Reference:** See [def.py:L640](file:///s:/MEGA/Scripts-Code/%23HEAVILY_USED/def/def.py#L640), [def.py:L704](file:///s:/MEGA/Scripts-Code/%23HEAVILY_USED/def/def.py#L704), and [def.py:L1232-1240](file:///s:/MEGA/Scripts-Code/%23HEAVILY_USED/def/def.py#L1232-1240).
- **Happy Path:** Closing a search or result window hides it immediately; the tray icon remains active, and hotkeys continue to work.
- **Bad Path:** Actually destroying the root window or exiting the Python process when clicking the `X` button or pressing `Escape`.

### 3. Thread Safety & Non-Blocking GUI
- **Mechanics:** All network requests (scraping Reverso/Vocab/API) and audio operations (downloading and playing pronunciations) **must** run on background daemon threads. When background threads complete, they must schedule UI updates on the main Tkinter thread using `root.after()`.
- **Code Reference:** See [def.py:L780](file:///s:/MEGA/Scripts-Code/%23HEAVILY_USED/def/def.py#L780), [def.py:L990](file:///s:/MEGA/Scripts-Code/%23HEAVILY_USED/def/def.py#L990), and [def.py:L1244-1249](file:///s:/MEGA/Scripts-Code/%23HEAVILY_USED/def/def.py#L1244-1249).
- **Happy Path:** The user interface remains responsive and shows visual animations during lookups or audio loading.
- **Bad Path:** Running network/audio calls directly on the main thread, freezing the window, displaying "Not Responding," or blocking the pynput hotkey listener.

### 4. Custom Focus Stealing (Windows)
- **Mechanics:** When the search window is triggered via the global hotkey, the app bypasses Windows foreground-lock restrictions by attaching thread input queues via User32 DLL functions. This forces focus to the Tkinter text entry box regardless of which application is currently active.
- **Code Reference:** See [def.py:L513-538](file:///s:/MEGA/Scripts-Code/%23HEAVILY_USED/def/def.py#L513-538).
- **Happy Path:** The search box appears instantly and is immediately focused and ready for typing.
- **Bad Path:** The window opens behind the active browser/IDE window, or opens in the foreground but does not receive keyboard focus, forcing the user to click it.

---

## ⚡ Core Features Specification

### 1. Global Hotkey Activation (`Ctrl+Alt+W`)
* **What it is:** A global shortcut that brings up the search input window from anywhere in the OS.
* **Happy Path:**
  1. Hitting `Ctrl+Alt+W` opens the search window.
  2. The input field is empty, focused, and ready for typing.
  3. Search history is visible underneath the entry box (up to 10 entries).
  4. Hitting `Escape` closes/hides the search window immediately.
* **Bad Path (What it IS NOT & must NOT do):**
  - **DO NOT** accumulate multiple windows.
  - **DO NOT** open the window without keyboard focus.
  - **DO NOT** persist the previous lookup term in the entry box when opening it fresh.

### 2. Clipboard Lookup (`Ctrl+Alt+D`)
* **What it is:** A global shortcut that grabs the current clipboard text and initiates an automatic lookup.
* **Happy Path:**
  1. User highlights a word in any program and copies it (or it is already on the clipboard).
  2. User presses `Ctrl+Alt+D`.
  3. The app opens, verifies the clipboard contents, and if it consists of 3 words or fewer, immediately initiates a search.
  4. If the clipboard is empty, has formatting issues, or has more than 3 words, the app falls back to opening a blank search window instead of throwing an error.
* **Bad Path (What it IS NOT & must NOT do):**
  - **DO NOT** automatically simulate `Ctrl+C` inputs directly on the user's OS; it must retrieve text from the clipboard via the Tkinter clipboard API.
  - **DO NOT** auto-search text containing more than 3 words, to prevent scraping sentences or entire paragraphs.

### 3. Multi-Source Scraping & Caching
* **What it is:** A hybrid dictionary backend utilizing both APIs and web-scraping to aggregate definition context.
* **Aggregated Sources:**
  - **Free Dictionary API:** Phonetics and structured parts of speech.
  - **Vocabulary.com:** Primary English short and long definitions.
  - **Reverso Context:** Arabic translation words and real-world example sentences.
* **Happy Path:**
  1. Check database (`cache.db`) for cached word. If present, load instantly.
  2. If missing, look up on all three services concurrently using `cloudscraper` (with Chrome/Windows headers to prevent Cloudflare challenges).
  3. Parse results, write JSON to `word_cache` SQLite table, and display results.
  4. If Vocabulary.com fails, fallback to the Free Dictionary API's first definition as the `short_def`.
* **Bad Path (What it IS NOT & must NOT do):**
  - **DO NOT** skip cache.db checking (causes unnecessary internet queries and risk of IP bans).
  - **DO NOT** throw raw exception windows if one service fails; degrade gracefully as long as at least one source (definitions or translations) succeeds.

### 4. Audio Pronunciation Playback
* **What it is:** Distinct buttons for UK (`🔊 UK`) and US (`🔊 US`) pronunciation playback using Windows MCI (`winmm.dll`).
* **Happy Path:**
  1. Clicking a sound button changes its label to a loading state (e.g. `⏳ UK`) and disables the button.
  2. Checks for a cached MP3/WAV file under the `audio_cache` directory.
  3. If not cached, downloads the audio from Google Translate TTS or the Dictionary API.
  4. Plays audio asynchronously and restores the button state immediately afterward.
  5. Uses MCI alias `myaudio` and locks thread playback via `_mci_lock` to ensure two audio clips do not clash.
* **Bad Path (What it IS NOT & must NOT do):**
  - **DO NOT** use command-line audio players (e.g., cmd/start/ffplay) that spawn separate cmd windows.
  - **DO NOT** leave file handles open on cached audio files (MCI must call `close myaudio` before playing a new file, otherwise the file stays locked and throws errors).

### 5. Smart Copy (`Ctrl+C` / "📋 Copy" button) vs. Copy All
* **What it is:** A custom-formatted clipboard exporter designed for quick note-taking.
* **Format:**
  ```text
  [Word]
  Arabic: [Translation 1] | [Translation 2] | ... (Max 8)
  Def 1: [Short Definition]
  Def 2: [Long Definition]
  ```
* **Happy Path:**
  1. Clicking "📋 Copy" (top-right overlay button) builds the clean multi-line summary block.
  2. Wipes clipboard and stores only this clean summary.
  3. Changes button text to `✓ Copied!` for 1.5 seconds.
  4. Clicking the bottom toolbar's "📋 Copy All" button copies the entire verbatim text of the ScrolledText box instead of the summary.
* **Bad Path (What it IS NOT & must NOT do):**
  - **DO NOT** include the UI elements (buttons, separators like "━━━", or credit labels) in the Smart Copy.
  - **DO NOT** format the Smart Copy with HTML or Markdown formatting unless requested. It must remain plain text.

### 6. Settings Panel
* **What it is:** GUI panel to configure hotkeys, clear database tables, and toggle startup registry run states.
* **Happy Path:**
  1. **Hotkeys:** Interactive key capturing (binds `<KeyPress>`, formats pynput key names). Saves to `settings.json`.
  2. **Cache:** Displays current text cache count and audio cache size/file count. Clicking clear deletes local files and SQLite rows.
  3. **Auto-Start:** Updates the Windows Registry key `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` to point to the correct path of `def.exe` (or `pythonw.exe def.py`).
* **Bad Path (What it IS NOT & must NOT do):**
  - **DO NOT** permit blank or single-key modifiers for hotkeys (e.g., just `W` or just `Ctrl` without a target key) to avoid locking up keys on the system.
  - **DO NOT** write invalid JSON files that crash the settings loader.

---

## ⚙️ Configuration & Packaging Specifications

### 1. File & Directory Layout
- **Database:** `cache.db` stored in `%APPDATA%\def` (Windows) or `~/.config/def` (others). Contains the `word_cache` table.
- **Settings:** `settings.json` stored in the same config directory.
- **Audio Cache:** `audio_cache/` directory under the config directory.
- **Logs:** `def.log` stored in the same config directory.
- **Code Reference:** See [def.py:L78-85](file:///s:/MEGA/Scripts-Code/%23HEAVILY_USED/def/def.py#L78-85) and [def.py:L256-272](file:///s:/MEGA/Scripts-Code/%23HEAVILY_USED/def/def.py#L256-272).

### 2. PyInstaller Packaging (`def.spec`)
- Must package as a windowed application (`console=False`).
- Asset inclusion: `app.png` is copied to the root of the distribution bundle.
- Hidden Imports: must include `pynput.keyboard._win32`, `pynput.mouse._win32`, and `PIL.IcoImagePlugin` to avoid runtime import crashes inside the executable.
- Code Reference: See [def.spec](file:///s:/MEGA/Scripts-Code/%23HEAVILY_USED/def/def.spec).

### 3. Inno Setup Installer (`installer.iss`)
- Performs installation to `{localappdata}\Programs\def` (does not require administrator access).
- Leverages `AppMutex=def_dictionary_mutex` to refuse/warn installation if the app is currently running.
- Restarts the app post-install.
- Code Reference: See [installer.iss](file:///s:/MEGA/Scripts-Code/%23HEAVILY_USED/def/installer.iss).
