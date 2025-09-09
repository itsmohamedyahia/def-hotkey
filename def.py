"""
Word Lookup App — show input window with Ctrl+Alt+W.
When Enter is pressed: input window disappears immediately.
If lookup succeeds -> show results window.
If lookup fails -> show an error dialog.
"""
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import scrolledtext, Toplevel, Entry, Label, messagebox
from pynput import keyboard
import cloudscraper
from bs4 import BeautifulSoup
import textwrap
import re
import arabic_reshaper
from bidi.algorithm import get_display
import pystray
from PIL import Image, ImageDraw, ImageFont
import time
import requests
import socket
import os
import argparse
import json

# Application display/config name (string "def").
# IMPORTANT: don't use the Python keyword `def` as a variable name — use APP_NAME instead.
APP_NAME = "def"


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
        print(f"Running as bundled app, base_path: {base_path}")
    except AttributeError:
        base_path = os.path.abspath(".")
        print(f"Running as script, base_path: {base_path}")

    full_path = os.path.join(base_path, relative_path)
    print(f"Looking for icon at: {full_path}")
    print(f"File exists: {os.path.exists(full_path)}")
    return full_path

# --- Startup Installer ---
def add_to_startup():
    """Adds the script to the OS's startup programs."""

    # This is the key: PyInstaller sets sys.frozen to True when running as a bundled app.
    is_frozen = getattr(sys, 'frozen', False)

    if is_frozen:
        # We are running as a compiled executable. The path is simply sys.executable.
        executable_path = os.path.abspath(sys.executable)
        command = f'"{executable_path}"'
    else:
        # We are running as a .py script.
        script_path = os.path.abspath(sys.argv[0])
        python_exe = sys.executable.replace("python.exe", "pythonw.exe") # Use pythonw for no console on Windows
        command = f'"{python_exe}" "{script_path}"'

    platform = sys.platform
    if platform == "win32":
        add_to_startup_windows(command)
    elif platform == "linux":
        add_to_startup_linux(command)
    elif platform == "darwin":
        add_to_startup_macos(command)
    else:
        print(f"Startup installation not supported on this platform: {platform}")


def add_to_startup_windows(command):
    """Adds the app to Windows startup via the registry."""
    try:
        import winreg
        key_path = r"Software\\Microsoft\\Windows\\CurrentVersion\\Run"
        reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)

        with reg_key:
            # Use APP_NAME as the registry value name so the app is easily identifiable
            winreg.SetValueEx(reg_key, APP_NAME, 0, winreg.REG_SZ, command)
        print(f"Successfully added {APP_NAME} to Windows startup.")
    except Exception as e:
        print(f"Error adding to Windows startup: {e}")


def add_to_startup_linux(command):
    """Adds a .desktop file to the autostart directory on Linux."""
    try:
        autostart_dir = os.path.expanduser("~/.config/autostart")
        if not os.path.exists(autostart_dir):
            os.makedirs(autostart_dir)

        desktop_entry = f"""
[Desktop Entry]
Type=Application
Name={APP_NAME}
Comment=Look up words with a custom shortcut
Exec={command}
Terminal=false
"""
        with open(os.path.join(autostart_dir, f"{APP_NAME}.desktop"), "w") as f:
            f.write(desktop_entry.strip())
        print(f"Successfully added {APP_NAME} to Linux startup.")
    except Exception as e:
        print(f"Error adding to Linux startup: {e}")


def add_to_startup_macos(command):
    """Creates a launchd .plist file for macOS startup. Note: requires splitting command."""
    try:
        # For plist, command needs to be split into an array of strings
        import shlex
        program_args = shlex.split(command)

        plist_name = f"com.user.{APP_NAME}.plist"
        launch_agents_dir = os.path.expanduser("~/Library/LaunchAgents")

        if not os.path.exists(launch_agents_dir):
            os.makedirs(launch_agents_dir)

        plist_content = f"""
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{plist_name}</string>
    <key>ProgramArguments</key>
    <array>
        {''.join(f'<string>{arg}</string>' for arg in program_args)}
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
        with open(os.path.join(launch_agents_dir, plist_name), "w") as f:
            f.write(plist_content.strip())
        print(f"Successfully added {APP_NAME} to macOS startup.")
        print("You may need to log out and back in for it to take effect.")
    except Exception as e:
        print(f"Error adding to macOS startup: {e}")


def get_config_path():
    """Gets the path to the app's config file in a cross-platform way."""
    if sys.platform == "win32":
        # C:\Users\<User>\AppData\Roaming\<APP_NAME>
        config_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), APP_NAME)
    else:
        # ~/.config/<APP_NAME>
        config_dir = os.path.join(os.path.expanduser('~'), '.config', APP_NAME)

    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "settings.json")


def setup_auto_start():
    """
    Checks if this is the first run. If it is, silently adds the app
    to startup and updates the config file.
    """
    config_path = get_config_path()
    config = {}
    # Read existing config to avoid overwriting it
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass  # Will create a new file below if reading fails

    if not config.get("startup_configured"):
        print(f"First run detected for startup. Adding {APP_NAME} to startup...")
        try:
            add_to_startup()
            config["startup_configured"] = True
            # Write the updated config back
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
            print("Successfully configured application for auto-start.")
        except Exception as e:
            print(f"Error: Could not add application to startup: {e}")


# --- Configuration ---
SPACE = 2
WRAP_WIDTH = 70

# --- Helper functions ---
def x_word_per_line(elements, x):
    lines_list = []
    if elements:
        for i in range(0, len(elements), x):
            lines_list.append(" ".join(elements[i:i+x]))
    return lines_list


def add_padding(text, space):
    return " " * space + text


def wrap_string(string, width):
    if string:
        return textwrap.wrap(string, width=width)
    return []

# --- Data fetcher ---
def get_word_data(word):
    """
    Returns:
      - dict with data (same shape as before) on success,
      - None if lookup completed successfully but no useful data found (word not found),
      - dict with {'network_error': True, 'error': '...'} if there was a network/connectivity problem.
    """
    results = {
        'short_def': None,
        'long_def': None,
        'ar_words': None,
        'eng_examples': None,
        'error': None
    }
    error_messages = []

    # Try to create scraper; treat failure here as a network/initialization problem
    try:
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False},
            delay=10
        )
    except Exception as e:
        return {'network_error': True, 'error': f'Cloudscraper init error: {e}'}

    # Helper to treat requests-related exceptions as network errors
    def treat_request_as_network(exc):
        # requests raises requests.exceptions.RequestException for many network issues.
        # Also treat socket.gaierror / OSError as network problems.
        return isinstance(exc, requests.exceptions.RequestException) or isinstance(exc, socket.gaierror) or isinstance(exc, OSError)

    # Vocabulary.com
    try:
        vocab_url = f"https://www.vocabulary.com/dictionary/{word}"
        response_vocab = scraper.get(vocab_url, timeout=25)
        response_vocab.raise_for_status()
        soup_vocab = BeautifulSoup(response_vocab.content, 'html.parser')
        short_def_tag = soup_vocab.find('p', class_='short')
        long_def_tag = soup_vocab.find('p', class_='long')
        results['short_def'] = " ".join(short_def_tag.stripped_strings) if short_def_tag else None
        results['long_def'] = " ".join(long_def_tag.stripped_strings) if long_def_tag else None
        if not results['short_def'] and not results['long_def']:
            error_messages.append(f"Vocabulary.com: Could not find definitions for '{word}'.")
    except Exception as e:
        # If this looks like a network error, return network sentinel immediately.
        if treat_request_as_network(e):
            return {'network_error': True, 'error': f'Vocabulary.com request failed: {e}'}
        error_messages.append(f"Vocabulary.com Error: {e}")

    # Reverso Context
    try:
        reverso_url = f"https://context.reverso.net/translation/english-arabic/{word}"
        response_reverso = scraper.get(reverso_url, timeout=25)
        response_reverso.raise_for_status()
        soup_reverso = BeautifulSoup(response_reverso.content, "html.parser")
        ar_words_tags = soup_reverso.select("span.display-term")
        eng_sents_tags = soup_reverso.select("div.example div.ltr span.text")
        results['ar_words'] = [el.get_text(strip=True) for el in ar_words_tags if el.get_text(strip=True)]

        # Use ' '.join(el.stripped_strings) to correctly handle spaces around highlighted words.
        results['eng_examples'] = [' '.join(el.stripped_strings) for el in eng_sents_tags if el.get_text(strip=True)]

        if not results['ar_words'] and not results['eng_examples']:
            error_messages.append(f"Reverso Context: Could not find translations or examples for '{word}'.")
    except Exception as e:
        if treat_request_as_network(e):
            return {'network_error': True, 'error': f'Reverso Context request failed: {e}'}
        error_messages.append(f"Reverso Context Error: {e}")

    if error_messages:
        results['error'] = "\n".join(error_messages)

    # If no useful data at all, return None to indicate lookup produced nothing useful
    if not any(v for k, v in results.items() if k != 'error' and v):
        return None

    return results

# --- Formatter ---
def format_data_for_display(search_word, data):
    if data is None:
        return f"Could not find any results for '{search_word}'."

    output_lines = []
    divider = "-" * 50

    # Arabic words
    output_lines.append(divider)
    if data.get('ar_words'):
        ar_lines = x_word_per_line(data['ar_words'], 5)
        for line in ar_lines:
            reshaped_text = arabic_reshaper.reshape(line)
            bidi_text = get_display(reshaped_text)
            output_lines.append(add_padding(bidi_text, SPACE))
    else:
        output_lines.append(add_padding("No Arabic translations found.", SPACE))

    # Short def
    output_lines.append(divider)
    if data.get('short_def'):
        short_def_lines = wrap_string(data['short_def'], WRAP_WIDTH)
        for line in short_def_lines:
            output_lines.append(add_padding(line, SPACE))
    else:
        output_lines.append(add_padding("No short definition found.", SPACE))

    # Long def
    output_lines.append(divider)
    if data.get('long_def'):
        long_def_lines = wrap_string(data['long_def'], WRAP_WIDTH)
        for line in long_def_lines:
            output_lines.append(add_padding(line, SPACE))
    else:
        output_lines.append(add_padding("No long definition found.", SPACE))

    # Examples
    output_lines.append(divider)
    if data.get('eng_examples'):
        for sentence in data['eng_examples']:
            wrapped_lines = wrap_string(sentence, WRAP_WIDTH)
            for line in wrapped_lines:
                # Simply add the line, no more asterisk highlighting.
                output_lines.append(add_padding(line, SPACE))
            output_lines.append("")  # blank line between examples
    else:
        output_lines.append(add_padding("No English examples found.", SPACE))

    output_lines.append(divider)

    if data.get('error'):
        output_lines.append("\nNotes / Errors:")
        output_lines.append(data['error'])

    return "\n".join(output_lines)

# --- App class ---
class WordLookupApp:
    def __init__(self, root):
        self.root = root
        try:
            self.root.title(APP_NAME)
        except Exception:
            pass
        self.root.withdraw()
        self.input_window = None
        self.result_window = None
        self.result_text_widget = None
        self.tray_icon = None

        # --- New Hotkey & Config Management ---
        self.config_path = get_config_path()
        self.config = {}
        self.default_hotkey = '<ctrl>+<alt>+w'
        self.hotkey = self.default_hotkey
        self.load_config()  # Load saved hotkey on startup

        self.hotkey_listener = None
        self.hotkey_thread = None
        # --- End New ---

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    self.config = json.load(f)
                self.hotkey = self.config.get('hotkey', self.default_hotkey)
                print(f"Loaded config. Hotkey is: {self.hotkey}")
            else:
                print("No config file found. Using default hotkey.")
                self.config = {'hotkey': self.default_hotkey}
                self.save_config()  # Save the default on first run
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading config file: {e}. Using default settings.")
            self.hotkey = self.default_hotkey
            self.config = {'hotkey': self.hotkey}

    def save_config(self):
        try:
            self.config['hotkey'] = self.hotkey
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            print(f"Config saved. Hotkey is now: {self.hotkey}")
        except IOError as e:
            print(f"Error saving config file: {e}")

    def show_input_window(self):
        if self.input_window and self.input_window.winfo_exists():
            self.input_window.lift()
            self.input_window.focus_force()
            self.entry.focus_set()
            return

        self.input_window = Toplevel(self.root)
        self.input_window.title(f"{APP_NAME}")

        if not hasattr(self, '_first_window_shown'):
            self.root.deiconify()
            self.root.withdraw()
            self._first_window_shown = True

        self.input_window.attributes("-topmost", True)

        window_width = 320
        window_height = 90
        screen_width = self.input_window.winfo_screenwidth()
        screen_height = self.input_window.winfo_screenheight()
        x_cordinate = int((screen_width / 2) - (window_width / 2))
        y_cordinate = int((screen_height / 2) - (window_height / 2))
        self.input_window.geometry(f"{window_width}x{window_height}+{x_cordinate}+{y_cordinate}")

        Label(self.input_window, text="Enter word to look up:").pack(pady=5)
        self.entry = Entry(self.input_window, width=40)
        self.entry.pack(pady=5, padx=10)
        self.input_window.lift()
        self.input_window.focus_force()
        self.entry.focus_set()

        self.input_window.after(50, self.entry.focus_force)
        try:
            self.input_window.grab_set()
        except Exception:
            pass

        self.entry.bind("<Return>", self.start_lookup)
        self.input_window.bind("<Escape>", lambda e: self.close_input_window())

    def close_input_window(self):
        try:
            if self.input_window and self.input_window.winfo_exists():
                try:
                    self.input_window.grab_release()
                except Exception:
                    pass
                self.input_window.destroy()
        except Exception:
            pass

    def start_lookup(self, event=None):
        word = self.entry.get().strip()
        if not word:
            return
        self.close_input_window()
        lookup_thread = threading.Thread(target=self.run_lookup_and_update_gui, args=(word,), daemon=True)
        lookup_thread.start()

    def run_lookup_and_update_gui(self, word):
        try:
            data = get_word_data(word)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Lookup error", f"An unexpected error occurred: {e}"))
            return

        if isinstance(data, dict) and data.get('network_error'):
            err_detail = data.get('error', 'Network error')
            self.root.after(0, lambda: messagebox.showerror("Network error",
                                                            f"Could not reach the lookup services.\nPlease check your internet connection.\n\nDetails: {err_detail}"))
            return

        if data is None:
            self.root.after(0, lambda: messagebox.showinfo("No results", f"No results found for '{word}'."))
            return

        formatted_results = format_data_for_display(word, data)
        self.root.after(0, lambda: self.display_results(formatted_results, f"Results for '{word}'", word))

    def close_result_window(self, event=None):
        try:
            if self.result_window and self.result_window.winfo_exists():
                self.result_window.destroy()
                self.result_window = None
                self.result_text_widget = None
        except Exception:
            pass

    def display_results(self, content, title="Results", search_word=None):
        if self.result_window and self.result_window.winfo_exists():
            try:
                self.result_window.destroy()
            except Exception:
                pass

        self.result_window = Toplevel(self.root)
        self.result_window.title(title)
        self.result_window.attributes("-topmost", True)

        self.result_text_widget = scrolledtext.ScrolledText(
            self.result_window, wrap=tk.WORD, width=80, height=25
        )
        self.result_text_widget.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        self.result_text_widget.insert(tk.INSERT, content)
        self.result_text_widget.config(state=tk.DISABLED)
        self.result_window.bind("<Escape>", lambda e: self.close_result_window())
        self.result_window.update_idletasks()
        win_w = self.result_window.winfo_width()
        win_h = self.result_window.winfo_height()
        screen_w = self.result_window.winfo_screenwidth()
        screen_h = self.result_window.winfo_screenheight()
        x = (screen_w // 2) - (win_w // 2)
        y = (screen_h // 2) - (win_h // 2)
        self.result_window.geometry(f"+{x}+{y}")

        self.result_window.lift()
        self.result_window.focus_force()
        self.result_window.after(200, lambda: self.result_window.attributes("-topmost", False))

    def create_tray_icon(self):
        possible_icons = ["app.png", "tray_icon.png", "app.ico"]
        img = None
        for icon_name in possible_icons:
            try:
                image_path = resource_path(icon_name)
                if os.path.exists(image_path):
                    img = Image.open(image_path)
                    print(f"Successfully loaded icon: {icon_name}")
                    break
            except Exception as e:
                print(f"Failed to load {icon_name}: {e}")
                continue

        if img is None:
            print("All icon loading attempts failed. Using fallback.")
            img = Image.new('RGB', (64, 64), color=(30, 144, 255))
            try:
                draw = ImageDraw.Draw(img)
                font = ImageFont.truetype("arial.ttf", 40)
                draw.text((20, 10), "W", fill=(255, 255, 255), font=font)
            except Exception:
                pass

        menu = pystray.Menu(
            pystray.MenuItem('Show', lambda: self.root.after(0, self.show_input_window)),
            pystray.MenuItem('Customize Shortcut', lambda: self.root.after(0, self.open_shortcut_window)),
            pystray.MenuItem('Exit', self.on_tray_exit)
        )

        icon = pystray.Icon(APP_NAME, img, APP_NAME, menu)
        self.tray_icon = icon

        def run_icon():
            try:
                icon.run()
            except Exception as e:
                print(f"Error running tray icon: {e}")

        t = threading.Thread(target=run_icon, daemon=True)
        t.start()

    def open_shortcut_window(self):
        if hasattr(self, 'shortcut_window') and self.shortcut_window.winfo_exists():
            self.shortcut_window.lift()
            self.shortcut_window.focus_force()
            return

        self.shortcut_window = Toplevel(self.root)
        self.shortcut_window.title("Customize Shortcut")
        self.shortcut_window.attributes("-topmost", True)
        self.shortcut_window.resizable(False, False)

        self.new_shortcut_var = tk.StringVar()
        self.new_shortcut_var.set(self.hotkey)

        Label(self.shortcut_window, text=f"Current Shortcut:", padx=20).pack(pady=(10, 0))
        Label(self.shortcut_window, text=f"{self.hotkey}", font=tkfont.Font(weight="bold")).pack()
        Label(self.shortcut_window, text="Click the box below and press your new combination:", padx=20).pack(pady=(15, 5))
        
        entry = Entry(self.shortcut_window, textvariable=self.new_shortcut_var, width=30, justify='center', font=tkfont.Font(size=12))
        entry.pack(pady=5, padx=20)

        def on_key_press(event):
            entry.config(state=tk.NORMAL)
            entry.delete(0, tk.END)
            modifiers = []
            if event.state & 0x0004: modifiers.append('<ctrl>')
            if event.state & 0x20000: modifiers.append('<alt>')
            if event.state & 0x0001: modifiers.append('<shift>')
            if sys.platform == "darwin" and event.state & 0x0008: modifiers.append('<cmd>')
            if sys.platform == "win32" and event.state & 0x0008: modifiers.append('<cmd>')

            key = event.keysym.lower()
            if key in ['control_l', 'control_r', 'alt_l', 'alt_r', 'shift_l', 'shift_r', 'super_l', 'super_r', 'meta_l', 'meta_r']:
                entry.config(state='readonly')
                return "break"
            
            main_key = f'<{key}>' if len(key) > 1 else key
            shortcut_parts = sorted(list(set(modifiers))) + [main_key]
            shortcut_str = "+".join(shortcut_parts)
            self.new_shortcut_var.set(shortcut_str)
            entry.config(state='readonly')
            return "break"

        entry.bind("<KeyPress>", on_key_press)
        entry.config(state='readonly')

        def save_and_close():
            new_shortcut = self.new_shortcut_var.get()
            if not new_shortcut or '+' not in new_shortcut:
                messagebox.showwarning("Invalid Shortcut", "Shortcut must include a modifier key (e.g., Ctrl, Alt) plus another key.", parent=self.shortcut_window)
                return
            self.restart_hotkey_listener(new_shortcut)
            self.shortcut_window.destroy()
            messagebox.showinfo("Success", f"Shortcut successfully changed to {new_shortcut}.")

        button_frame = tk.Frame(self.shortcut_window)
        button_frame.pack(pady=10, padx=20, fill='x')
        tk.Button(button_frame, text="Save", command=save_and_close).pack(side=tk.RIGHT, padx=5)
        tk.Button(button_frame, text="Cancel", command=self.shortcut_window.destroy).pack(side=tk.RIGHT)

        self.shortcut_window.update_idletasks()
        x = (self.shortcut_window.winfo_screenwidth() // 2) - (self.shortcut_window.winfo_width() // 2)
        y = (self.shortcut_window.winfo_screenheight() // 2) - (self.shortcut_window.winfo_height() // 2)
        self.shortcut_window.geometry(f'+{x}+{y}')
        entry.focus_set()

    def on_tray_exit(self):
        self.root.after(0, self.on_close)

    def on_close(self):
        try:
            if self.tray_icon: self.tray_icon.stop()
            if self.hotkey_listener: self.hotkey_listener.stop()
        finally:
            self.root.destroy()

    def start_hotkey_listener(self, hotkey_string):
        """ This method runs in a dedicated thread and blocks until stopped. """
        print(f"Thread started for hotkey: {hotkey_string}")

        def on_hotkey_activated():
            print(f"Hotkey '{self.hotkey}' activated!")
            if hasattr(self, 'root') and self.root:
                self.root.after(0, self.show_input_window)
        
        try:
            hotkeys = {hotkey_string: on_hotkey_activated}
            listener = keyboard.GlobalHotKeys(hotkeys)
            self.hotkey_listener = listener
            listener.run()  # This is a blocking call, perfect for a thread
            print(f"Listener for '{hotkey_string}' has stopped.")
        except Exception as e:
            print(f"ERROR in hotkey thread for '{hotkey_string}': {e}")
            self.root.after(0, lambda: messagebox.showerror(
                "Hotkey Error",
                f"Failed to register hotkey '{hotkey_string}'. It might be in use by another application."
            ))
    
    def restart_hotkey_listener(self, new_hotkey):
        """ Stops the current listener and starts a new one in a new thread. """
        self.hotkey = new_hotkey
        self.save_config()

        if self.hotkey_listener:
            self.hotkey_listener.stop()
            print("Signaled old listener to stop.")

        self.hotkey_thread = threading.Thread(target=self.start_hotkey_listener, args=(self.hotkey,), daemon=True)
        self.hotkey_thread.start()
        print("Started new hotkey listener thread.")

# --- Main execution ---
def main():
    global app
    print(f"Starting {APP_NAME}...")

    # Silently configure auto-start on the first run.
    setup_auto_start()

    root = tk.Tk()
    app = WordLookupApp(root)
    print("App initialized")

    # Start the initial hotkey listener based on loaded config
    app.restart_hotkey_listener(app.hotkey)

    try:
        app.create_tray_icon()
        print("Tray icon created")
    except Exception as e:
        print(f"Could not create tray icon: {e}")

    print("Starting main loop...")
    try:
        root.mainloop()
    finally:
        print("Shutting down...")
        try:
            if hasattr(app, 'hotkey_listener') and app.hotkey_listener:
                app.hotkey_listener.stop()
            if hasattr(app, 'tray_icon') and app.tray_icon:
                app.tray_icon.stop()
        except Exception:
            pass
        sys.exit(0)

if __name__ == '__main__':
    main()