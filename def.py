"""
Word Lookup App — show input window with Ctrl+Alt+W.
Highly Optimized for Reliability and Instant Window Focus.
"""
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import scrolledtext, Toplevel, Entry, Label, messagebox, Button
from pynput import keyboard
import cloudscraper
from bs4 import BeautifulSoup
import textwrap
import arabic_reshaper
from bidi.algorithm import get_display
import pystray
from PIL import Image, ImageDraw, ImageFont
import requests
import socket
import os
import json

# Application display/config name (string "def").
APP_NAME = "def"

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- Startup Installer ---
def add_to_startup():
    is_frozen = getattr(sys, 'frozen', False)
    if is_frozen:
        command = f'"{os.path.abspath(sys.executable)}"'
    else:
        command = f'"{sys.executable.replace("python.exe", "pythonw.exe")}" "{os.path.abspath(sys.argv[0])}"'

    if sys.platform == "win32":
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            with reg_key:
                winreg.SetValueEx(reg_key, APP_NAME, 0, winreg.REG_SZ, command)
        except Exception:
            pass

def get_config_path():
    if sys.platform == "win32":
        config_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), APP_NAME)
    else:
        config_dir = os.path.join(os.path.expanduser('~'), '.config', APP_NAME)
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "settings.json")

def setup_auto_start():
    config_path = get_config_path()
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f: config = json.load(f)
        except: pass
    if not config.get("startup_configured"):
        try:
            add_to_startup()
            config["startup_configured"] = True
            with open(config_path, 'w') as f: json.dump(config, f, indent=4)
        except: pass

# --- Configuration ---
SPACE = 2
WRAP_WIDTH = 70

def wrap_string(string, width):
    return textwrap.wrap(string, width=width) if string else []

# --- Data fetcher ---
def get_word_data(word):
    results = {'short_def': None, 'long_def': None, 'ar_words': None, 'eng_examples': None, 'error': None}
    error_messages = []

    try:
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}, delay=10)
    except Exception as e:
        return {'network_error': True, 'error': f'Cloudscraper init error: {e}'}

    # 1. Fallback API for English Definitions (Highly Reliable)
    try:
        api_url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        api_resp = requests.get(api_url, timeout=5)
        if api_resp.status_code == 200:
            data = api_resp.json()[0]
            meanings = data.get("meanings", [])
            if meanings:
                results['short_def'] = meanings[0]["definitions"][0].get("definition")
    except Exception:
        pass

    # 2. Vocabulary.com (For better long definitions if available)
    try:
        vocab_url = f"https://www.vocabulary.com/dictionary/{word}"
        response_vocab = scraper.get(vocab_url, timeout=10)
        if response_vocab.status_code == 200:
            soup_vocab = BeautifulSoup(response_vocab.content, 'html.parser')
            short_def_tag = soup_vocab.find('p', class_='short')
            long_def_tag = soup_vocab.find('p', class_='long')
            if short_def_tag and not results['short_def']:
                results['short_def'] = " ".join(short_def_tag.stripped_strings)
            if long_def_tag:
                results['long_def'] = " ".join(long_def_tag.stripped_strings)
    except Exception as e:
        error_messages.append(f"Vocab.com warning: {e}")

    # 3. Reverso Context (Arabic translation)
    try:
        reverso_url = f"https://context.reverso.net/translation/english-arabic/{word}"
        response_reverso = scraper.get(reverso_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        if response_reverso.status_code == 200:
            soup_reverso = BeautifulSoup(response_reverso.content, "html.parser")
            ar_words_tags = soup_reverso.select("span.display-term")
            eng_sents_tags = soup_reverso.select("div.example div.ltr span.text")
            results['ar_words'] = [el.get_text(strip=True) for el in ar_words_tags if el.get_text(strip=True)]
            results['eng_examples'] = [' '.join(el.stripped_strings) for el in eng_sents_tags if el.get_text(strip=True)]
    except Exception as e:
        error_messages.append(f"Reverso Context warning: {e}")

    if error_messages and not (results['short_def'] or results['ar_words']):
        results['error'] = "\n".join(error_messages)

    if not any(v for k, v in results.items() if k != 'error' and v):
        return None

    return results

# --- Formatter ---
def format_data_for_display(search_word, data):
    if data is None: return f"Could not find any results for '{search_word}'."
    output_lines = []
    divider = "-" * 50

    output_lines.append(divider)
    if data.get('ar_words'):
        ar_words_str = " | ".join(data['ar_words'][:5])
        bidi_text = get_display(arabic_reshaper.reshape(ar_words_str))
        output_lines.append("  " + bidi_text)
    else:
        output_lines.append("  No Arabic translations found.")

    output_lines.append(divider)
    if data.get('short_def'):
        for line in wrap_string(data['short_def'], WRAP_WIDTH): output_lines.append("  " + line)
    else:
        output_lines.append("  No short definition found.")

    if data.get('long_def'):
        output_lines.append(divider)
        for line in wrap_string(data['long_def'], WRAP_WIDTH): output_lines.append("  " + line)

    output_lines.append(divider)
    if data.get('eng_examples'):
        for sentence in data['eng_examples'][:3]:  # Limit to 3 examples
            for line in wrap_string(sentence, WRAP_WIDTH): output_lines.append("  " + line)
            output_lines.append("")
    else:
        output_lines.append("  No English examples found.")

    output_lines.append(divider)
    return "\n".join(output_lines)

# --- App class ---
class WordLookupApp:
    def __init__(self, root):
        self.root = root
        self.root.withdraw()
        self.base_font_size = 20
        self.app_font = tkfont.Font(family="Arial", size=self.base_font_size)

        self.config_path = get_config_path()
        self.default_hotkey = '<ctrl>+<alt>+w'
        self.hotkey = self.default_hotkey
        self.load_config()

        self.hotkey_listener = None
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Setup persistent windows
        self.setup_input_window()
        self.setup_result_window()

    def load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    self.hotkey = json.load(f).get('hotkey', self.default_hotkey)
            else:
                self.save_config()
        except: pass

    def save_config(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump({'hotkey': self.hotkey}, f, indent=4)
        except: pass

    def setup_input_window(self):
        """Create the input window once and keep it in memory."""
        self.input_window = Toplevel(self.root)
        self.input_window.title(APP_NAME)
        self.input_window.withdraw() # Hide initially
        self.input_window.attributes("-topmost", True)
        self.input_window.resizable(False, False)
        self.input_window.protocol("WM_DELETE_WINDOW", self.hide_input_window)

        window_width, window_height = 500, 140
        x = int((self.input_window.winfo_screenwidth() / 2) - (window_width / 2))
        y = int((self.input_window.winfo_screenheight() / 2) - (window_height / 2))
        self.input_window.geometry(f"{window_width}x{window_height}+{x}+{y}")

        self.input_label = Label(self.input_window, text="Enter word to look up:", font=self.app_font)
        self.input_label.pack(pady=5)
        
        self.entry = Entry(self.input_window, width=30, font=self.app_font)
        self.entry.pack(pady=5, padx=10)

        self.entry.bind("<Return>", self.start_lookup)
        self.input_window.bind("<Escape>", lambda e: self.hide_input_window())

    def setup_result_window(self):
        """Create the result window once and keep it in memory."""
        self.result_window = Toplevel(self.root)
        self.result_window.title("Results")
        self.result_window.withdraw()
        self.result_window.attributes("-topmost", True)
        self.result_window.protocol("WM_DELETE_WINDOW", self.hide_result_window)

        self.result_text_widget = scrolledtext.ScrolledText(self.result_window, wrap=tk.WORD, width=60, height=15, font=self.app_font)
        self.result_text_widget.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        self.result_text_widget.bind("<Control-MouseWheel>", self.zoom_text)
        self.result_text_widget.bind("<Control-Button-4>", lambda e: self.zoom_text(e, 1))
        self.result_text_widget.bind("<Control-Button-5>", lambda e: self.zoom_text(e, -1))
        self.result_window.bind("<Escape>", lambda e: self.hide_result_window())

        zoom_frame = tk.Frame(self.result_window, bg="#ddd")
        zoom_frame.place(relx=1.0, rely=0.0, anchor="ne", x=-25, y=10)
        Button(zoom_frame, text="+", font=("Arial", 12, "bold"), width=2, command=lambda: self.zoom_text(direction=1)).pack(side=tk.LEFT, padx=1)
        Button(zoom_frame, text="-", font=("Arial", 12, "bold"), width=2, command=lambda: self.zoom_text(direction=-1)).pack(side=tk.LEFT, padx=1)

        win_w, win_h = 800, 500
        x = (self.result_window.winfo_screenwidth() // 2) - (win_w // 2)
        y = (self.result_window.winfo_screenheight() // 2) - (win_h // 2)
        self.result_window.geometry(f"{win_w}x{win_h}+{x}+{y}")

    def steal_windows_focus(self, window):
        """HACK: Bypasses Windows Foreground Lock Timeout (The Orange Flashing Icon Fix)"""
        if sys.platform == "win32":
            try:
                import ctypes
                # Simulate pressing the ALT key to trick Windows into allowing focus steal
                ctypes.windll.user32.keybd_event(0x12, 0, 0, 0) # Alt Down
                ctypes.windll.user32.keybd_event(0x12, 0, 2, 0) # Alt Up
                # Force window to foreground
                hwnd = int(window.frame(), 16)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception as e:
                print(f"Focus steal failed: {e}")

    def show_input_window(self):
        self.hide_result_window() # Close results if open
        self.input_label.config(text="Enter word to look up:")
        self.entry.config(state=tk.NORMAL)
        self.entry.delete(0, tk.END)
        
        self.input_window.deiconify()
        self.input_window.attributes("-topmost", True)
        
        # Apply Focus Fix
        self.steal_windows_focus(self.input_window)
        
        self.input_window.lift()
        self.entry.focus_force()

    def hide_input_window(self):
        self.input_window.withdraw()

    def hide_result_window(self):
        self.result_window.withdraw()

    def start_lookup(self, event=None):
        word = self.entry.get().strip()
        if not word: return
        
        # Show a loading state instead of instantly vanishing
        self.entry.config(state=tk.DISABLED)
        self.input_label.config(text=f"Searching for '{word}'...")
        self.input_window.update()

        threading.Thread(target=self.run_lookup, args=(word,), daemon=True).start()

    def run_lookup(self, word):
        try:
            data = get_word_data(word)
        except Exception as e:
            self.root.after(0, lambda: self.show_error(f"An unexpected error occurred: {e}"))
            return

        if isinstance(data, dict) and data.get('network_error'):
            self.root.after(0, lambda: self.show_error(f"Network error: {data.get('error')}"))
            return

        if data is None:
            self.root.after(0, lambda: self.show_error(f"No results found for '{word}'."))
            return

        formatted = format_data_for_display(word, data)
        self.root.after(0, lambda: self.display_results(formatted, f"Results for '{word}'"))

    def show_error(self, message):
        self.hide_input_window()
        messagebox.showerror("Lookup Error", message)

    def display_results(self, content, title):
        self.hide_input_window() # Hide input now that we have results
        
        self.result_window.title(title)
        self.result_text_widget.config(state=tk.NORMAL)
        self.result_text_widget.delete(1.0, tk.END)
        self.result_text_widget.insert(tk.INSERT, content)
        self.result_text_widget.config(state=tk.DISABLED)
        
        self.result_window.deiconify()
        self.result_window.attributes("-topmost", True)
        
        # Apply Focus Fix to Results Window
        self.steal_windows_focus(self.result_window)
        
        self.result_window.lift()
        self.result_window.focus_force()

    def zoom_text(self, event=None, direction=0):
        if event:
            if event.delta: direction = 1 if event.delta > 0 else -1
            elif event.num == 4: direction = 1
            elif event.num == 5: direction = -1
        new_size = max(8, min(72, self.app_font.cget("size") + (direction * 2)))
        self.app_font.configure(size=new_size)

    def create_tray_icon(self):
        img = Image.new('RGB', (64, 64), color=(30, 144, 255))
        try:
            draw = ImageDraw.Draw(img)
            draw.text((15, 10), "W", fill=(255, 255, 255), font=ImageFont.truetype("arial.ttf", 40))
        except: pass

        for icon_name in ["app.png", "tray_icon.png", "app.ico"]:
            try:
                path = resource_path(icon_name)
                if os.path.exists(path):
                    img = Image.open(path)
                    break
            except: pass

        menu = pystray.Menu(
            pystray.MenuItem('Show', lambda: self.root.after(0, self.show_input_window)),
            pystray.MenuItem('Customize Shortcut', lambda: self.root.after(0, self.open_shortcut_window)),
            pystray.MenuItem('Exit', self.on_tray_exit)
        )
        self.tray_icon = pystray.Icon(APP_NAME, img, APP_NAME, menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def open_shortcut_window(self):
        win = Toplevel(self.root)
        win.title("Customize Shortcut")
        win.attributes("-topmost", True)
        self.steal_windows_focus(win)
        win.focus_force()

        var = tk.StringVar(value=self.hotkey)
        Label(win, text=f"Current: {self.hotkey}", font=("Arial", 12, "bold")).pack(pady=(10, 0))
        Label(win, text="Press new combination:").pack(pady=5)
        
        entry = Entry(win, textvariable=var, width=30, justify='center', font=("Arial", 12))
        entry.pack(pady=5, padx=20)

        def on_key(e):
            mods = []
            if e.state & 0x0004: mods.append('<ctrl>')
            if e.state & 0x20000: mods.append('<alt>')
            if e.state & 0x0001: mods.append('<shift>')
            key = e.keysym.lower()
            if key not in ['control_l', 'control_r', 'alt_l', 'alt_r', 'shift_l', 'shift_r']:
                var.set("+".join(sorted(set(mods)) + [f'<{key}>' if len(key)>1 else key]))
            return "break"

        entry.bind("<KeyPress>", on_key)
        
        def save():
            if '+' in var.get():
                self.restart_hotkey_listener(var.get())
                win.destroy()
                messagebox.showinfo("Success", f"Shortcut changed to {var.get()}")

        tk.Button(win, text="Save", command=save).pack(pady=10)
        entry.focus_set()

    def on_tray_exit(self):
        self.root.after(0, self.on_close)

    def on_close(self):
        if self.tray_icon: self.tray_icon.stop()
        if self.hotkey_listener: self.hotkey_listener.stop()
        self.root.destroy()

    def start_hotkey_listener(self, hotkey_string):
        def on_activate():
            self.root.after(0, self.show_input_window)
        try:
            self.hotkey_listener = keyboard.GlobalHotKeys({hotkey_string: on_activate})
            self.hotkey_listener.run()
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Hotkey Error", f"Failed to register '{hotkey_string}'. Error: {e}"))
    
    def restart_hotkey_listener(self, new_hotkey):
        self.hotkey = new_hotkey
        self.save_config()
        if self.hotkey_listener: self.hotkey_listener.stop()
        threading.Thread(target=self.start_hotkey_listener, args=(self.hotkey,), daemon=True).start()

def main():
    setup_auto_start()
    root = tk.Tk()
    app = WordLookupApp(root)
    app.restart_hotkey_listener(app.hotkey)
    app.create_tray_icon()
    root.mainloop()

if __name__ == '__main__':
    main()