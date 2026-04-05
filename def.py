"""
Word Lookup App — show input window with Ctrl+Alt+W.
Clipboard lookup with Ctrl+Alt+D.
Dark-themed, feature-rich dictionary with search history and caching.
"""
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import scrolledtext, Toplevel, Entry, Label, Button
from pynput import keyboard
import cloudscraper
from bs4 import BeautifulSoup
import arabic_reshaper
from bidi.algorithm import get_display
import pystray
from PIL import Image, ImageDraw, ImageFont
import requests
import socket
import os
import json

APP_NAME = "def"

# --- Dark Theme Colors (Catppuccin Mocha) ---
C = {
    'bg':       '#1e1e2e',
    'surface':  '#313244',
    'overlay':  '#45475a',
    'text':     '#cdd6f4',
    'subtext':  '#a6adc8',
    'blue':     '#89b4fa',
    'green':    '#a6e3a1',
    'gold':     '#f9e2af',
    'red':      '#f38ba8',
    'mauve':    '#cba6f7',
    'teal':     '#94e2d5',
    'peach':    '#fab387',
    'lavender': '#b4befe',
}


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
            with open(config_path, 'r') as f:
                config = json.load(f)
        except Exception:
            pass
    if not config.get("startup_configured"):
        try:
            add_to_startup()
            config["startup_configured"] = True
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception:
            pass


def check_connectivity():
    """Quick internet connectivity check."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        return True
    except OSError:
        return False


# --- Data fetcher ---
def get_word_data(word):
    """Fetch word data from multiple sources. Returns structured dict."""
    results = {
        'short_def': None, 'long_def': None, 'ar_words': None,
        'eng_examples': None, 'error': None, 'phonetic': None,
        'meanings': [], 'audio_url': None,
    }
    error_messages = []
    api_fallback_short_def = None

    try:
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}, delay=10
        )
    except Exception as e:
        return {'network_error': True, 'error': f'Cloudscraper init error: {e}'}

    # 1. Free Dictionary API — extracts phonetics, synonyms, and additional structured meanings
    try:
        api_resp = requests.get(
            f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=5
        )
        if api_resp.status_code == 200:
            data = api_resp.json()[0]
            results['phonetic'] = data.get('phonetic')
            for p in data.get('phonetics', []):
                if p.get('audio'):
                    results['audio_url'] = p['audio']
                    break
            for m in data.get('meanings', []):
                meaning = {
                    'pos': m.get('partOfSpeech', ''),
                    'definitions': [],
                    'synonyms': list(dict.fromkeys(m.get('synonyms', [])))[:6],
                    'antonyms': list(dict.fromkeys(m.get('antonyms', [])))[:6],
                }
                for d in m.get('definitions', [])[:3]:
                    meaning['definitions'].append({
                        'text': d.get('definition', ''),
                        'example': d.get('example'),
                    })
                results['meanings'].append(meaning)
            # Save API definition just in case Vocab.com fails
            if results['meanings'] and results['meanings'][0]['definitions']:
                api_fallback_short_def = results['meanings'][0]['definitions'][0]['text']
    except Exception:
        pass

    # 2. Vocabulary.com — primary source for high-quality short/long definitions
    try:
        resp = scraper.get(f"https://www.vocabulary.com/dictionary/{word}", timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'html.parser')
            short_tag = soup.find('p', class_='short')
            long_tag = soup.find('p', class_='long')
            if short_tag:
                results['short_def'] = " ".join(short_tag.stripped_strings)
            if long_tag:
                results['long_def'] = " ".join(long_tag.stripped_strings)
    except Exception as e:
        error_messages.append(f"Vocab.com: {e}")

    # Fallback: if Vocab.com had no short definition, use the API's definition
    if not results['short_def'] and api_fallback_short_def:
        results['short_def'] = api_fallback_short_def

    # 3. Reverso Context — Arabic translation + examples
    try:
        reverso_url = f"https://context.reverso.net/translation/english-arabic/{word}"
        response_reverso = scraper.get(reverso_url, timeout=25)
        response_reverso.raise_for_status()
        soup_reverso = BeautifulSoup(response_reverso.content, "html.parser")
        
        ar_words_tags = soup_reverso.select("span.display-term")
        eng_sents_tags = soup_reverso.select("div.example div.ltr span.text")
        
        results['ar_words'] = [el.get_text(strip=True) for el in ar_words_tags if el.get_text(strip=True)]
        results['eng_examples'] = [' '.join(el.stripped_strings) for el in eng_sents_tags if el.get_text(strip=True)]
    except Exception as e:
        error_messages.append(f"Reverso Context: {e}")

    if error_messages and not (results['short_def'] or results['ar_words']):
        results['error'] = "\n".join(error_messages)

    has_data = any(v for k, v in results.items() if k not in ('error', 'audio_url', 'phonetic') and v)
    return results if has_data else None


# --- App class ---
class WordLookupApp:
    MAX_HISTORY = 20

    def __init__(self, root):
        self.root = root
        self.root.withdraw()
        self.base_font_size = 18
        self.app_font = tkfont.Font(family="Segoe UI", size=self.base_font_size)

        self.config_path = get_config_path()
        self.default_hotkey = '<ctrl>+<alt>+w'
        self.default_clip_hotkey = '<ctrl>+<alt>+d'
        self.hotkey = self.default_hotkey
        self.clip_hotkey = self.default_clip_hotkey
        self.history = []
        self.cache = {}
        self._loading = False

        self.load_config()

        self.hotkey_listener = None
        self.tray_icon = None
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.setup_input_window()
        self.setup_result_window()

    # --- Config ---
    def load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    cfg = json.load(f)
                self.hotkey = cfg.get('hotkey', self.default_hotkey)
                self.clip_hotkey = cfg.get('clip_hotkey', self.default_clip_hotkey)
                self.history = cfg.get('history', [])
            else:
                self.save_config()
        except Exception:
            pass

    def save_config(self):
        try:
            existing = {}
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    existing = json.load(f)
            existing.update({
                'hotkey': self.hotkey,
                'clip_hotkey': self.clip_hotkey,
                'history': self.history[:self.MAX_HISTORY],
            })
            with open(self.config_path, 'w') as f:
                json.dump(existing, f, indent=4)
        except Exception:
            pass

    def add_to_history(self, word):
        w = word.strip().lower()
        if w in self.history:
            self.history.remove(w)
        self.history.insert(0, w)
        self.history = self.history[:self.MAX_HISTORY]
        self.save_config()

    # --- Helpers ---
    def _center(self, window, w, h):
        x = (window.winfo_screenwidth() // 2) - (w // 2)
        y = (window.winfo_screenheight() // 2) - (h // 2)
        window.geometry(f"{w}x{h}+{x}+{y}")

    def _steal_focus(self, window):
        if sys.platform != "win32":
            return
        try:
            import ctypes
            u32 = ctypes.windll.user32
            k32 = ctypes.windll.kernel32
            hwnd = int(window.frame(), 16)
            fg = u32.GetForegroundWindow()
            if hwnd == fg:
                return
            app_t = k32.GetCurrentThreadId()
            fg_t = u32.GetWindowThreadProcessId(fg, None)
            if fg_t != app_t and fg_t != 0:
                u32.AttachThreadInput(app_t, fg_t, True)
                u32.BringWindowToTop(hwnd)
                u32.ShowWindow(hwnd, 5)
                u32.SetForegroundWindow(hwnd)
                u32.AttachThreadInput(app_t, fg_t, False)
            else:
                u32.BringWindowToTop(hwnd)
                u32.ShowWindow(hwnd, 5)
                u32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def _show_window(self, window):
        window.attributes("-topmost", True)
        window.deiconify()
        self._steal_focus(window)
        window.lift()
        window.focus_force()
        window.after(200, lambda: window.attributes("-topmost", False))

    # --- Input Window ---
    def setup_input_window(self):
        win = Toplevel(self.root)
        win.title(APP_NAME)
        win.withdraw()
        win.resizable(False, False)
        win.configure(bg=C['bg'])
        win.protocol("WM_DELETE_WINDOW", self.hide_input_window)
        self.input_window = win

        f = tk.Frame(win, bg=C['bg'])
        f.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        self.input_label = Label(
            f, text="Look up a word",
            font=("Segoe UI", 22, "bold"), bg=C['bg'], fg=C['blue']
        )
        self.input_label.pack(pady=(0, 8))

        ef = tk.Frame(f, bg=C['overlay'], highlightthickness=2,
                      highlightbackground=C['overlay'], highlightcolor=C['blue'])
        ef.pack(fill=tk.X, pady=(0, 3))

        self.entry = Entry(
            ef, font=self.app_font,
            bg=C['surface'], fg=C['text'], insertbackground=C['text'],
            selectbackground=C['blue'], selectforeground=C['bg'],
            relief=tk.FLAT, bd=8
        )
        self.entry.pack(fill=tk.X)

        self.status_label = Label(
            f, text="", font=("Segoe UI", 10), bg=C['bg'], fg=C['subtext']
        )
        self.status_label.pack(pady=(2, 5))

        # History section
        self.history_frame = tk.Frame(f, bg=C['bg'])

        hdr = tk.Frame(self.history_frame, bg=C['bg'])
        hdr.pack(fill=tk.X)
        Label(hdr, text="Recent searches", font=("Segoe UI", 10),
              bg=C['bg'], fg=C['subtext']).pack(side=tk.LEFT)
        clr = Label(hdr, text="Clear", font=("Segoe UI", 10, "underline"),
                     bg=C['bg'], fg=C['overlay'], cursor="hand2")
        clr.pack(side=tk.RIGHT)
        clr.bind("<Button-1>", lambda e: self._clear_history())

        self.history_listbox = tk.Listbox(
            self.history_frame, font=("Segoe UI", 13),
            bg=C['surface'], fg=C['text'], selectbackground=C['blue'],
            selectforeground=C['bg'], relief=tk.FLAT, bd=4,
            highlightthickness=0, activestyle='none', height=7, cursor="hand2"
        )
        self.history_listbox.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        self.history_listbox.bind("<Double-Button-1>", self._on_history_select)
        self.history_listbox.bind("<Return>", self._on_history_select)

        self.entry.bind("<Return>", self.start_lookup)
        win.bind("<Escape>", lambda e: self.hide_input_window())

        self._center(win, 520, 380)

    def _refresh_history(self):
        self.history_listbox.delete(0, tk.END)
        for w in self.history[:10]:
            self.history_listbox.insert(tk.END, f"  {w}")
        if self.history:
            self.history_frame.pack(fill=tk.BOTH, expand=True)
            self._center(self.input_window, 520, 380)
        else:
            self.history_frame.pack_forget()
            self._center(self.input_window, 520, 160)

    def _clear_history(self):
        self.history = []
        self.save_config()
        self._refresh_history()

    def _on_history_select(self, event=None):
        sel = self.history_listbox.curselection()
        if sel:
            word = self.history_listbox.get(sel[0]).strip()
            self.entry.delete(0, tk.END)
            self.entry.insert(0, word)
            self.start_lookup()

    # --- Result Window ---
    def setup_result_window(self):
        win = Toplevel(self.root)
        win.title("Results")
        win.withdraw()
        win.configure(bg=C['bg'])
        win.protocol("WM_DELETE_WINDOW", self.hide_result_window)
        self.result_window = win

        # Container so we can overlay the smart-copy button
        text_container = tk.Frame(win, bg=C['bg'])
        text_container.pack(fill=tk.BOTH, expand=True)

        self.result_text = scrolledtext.ScrolledText(
            text_container, wrap=tk.WORD, font=self.app_font,
            bg=C['bg'], fg=C['text'], insertbackground=C['text'],
            selectbackground=C['blue'], selectforeground=C['bg'],
            relief=tk.FLAT, bd=0, padx=20, pady=15, highlightthickness=0,
        )
        self.result_text.pack(fill=tk.BOTH, expand=True)
        self._setup_tags()

        # Smart-copy button — top-right overlay
        self._current_word = ""
        self._current_data = {}
        self.smart_copy_btn = tk.Button(
            text_container, text="\U0001F4CB Copy",
            font=("Segoe UI", 10, "bold"),
            bg=C['surface'], fg=C['blue'],
            activebackground=C['overlay'], activeforeground=C['blue'],
            relief=tk.FLAT, bd=0, cursor="hand2", padx=10, pady=4,
            command=self._copy_smart,
        )
        self.smart_copy_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-8, y=8)

        # Bottom toolbar
        bar = tk.Frame(win, bg=C['surface'], height=45)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)

        bs = dict(
            font=("Segoe UI", 11), relief=tk.FLAT, bd=0, cursor="hand2",
            bg=C['surface'], fg=C['text'],
            activebackground=C['overlay'], activeforeground=C['text'],
            padx=12, pady=6,
        )
        Button(bar, text="\U0001F50D Search Again", command=self._search_again, **bs).pack(
            side=tk.LEFT, padx=(10, 5), pady=6)
        self.copy_btn = Button(bar, text="\U0001F4CB Copy All", command=self._copy, **bs)
        self.copy_btn.pack(side=tk.LEFT, padx=5, pady=6)

        self.zoom_label = Label(bar, text="100%", font=("Segoe UI", 10),
                                bg=C['surface'], fg=C['subtext'])
        self.zoom_label.pack(side=tk.RIGHT, padx=(0, 10))
        zbs = {**bs, 'font': ("Segoe UI", 13, "bold")}
        Button(bar, text="\u2212", width=3, command=lambda: self._zoom(d=-1), **zbs).pack(
            side=tk.RIGHT, padx=2, pady=6)
        Button(bar, text="+", width=3, command=lambda: self._zoom(d=1), **zbs).pack(
            side=tk.RIGHT, padx=2, pady=6)

        self.result_text.bind("<Control-MouseWheel>", self._zoom)
        self.result_text.bind("<Control-Button-4>", lambda e: self._zoom(d=1))
        self.result_text.bind("<Control-Button-5>", lambda e: self._zoom(d=-1))
        win.bind("<Escape>", lambda e: self.hide_result_window())
        win.bind("<Control-n>", lambda e: self._search_again())

        self._center(win, 850, 550)

    def _setup_tags(self):
        t = self.result_text
        sz = self.base_font_size
        t.tag_configure("title",    font=("Segoe UI", 26, "bold"), foreground=C['blue'], spacing3=2)
        t.tag_configure("ipa",      font=("Segoe UI", 15), foreground=C['subtext'])
        t.tag_configure("arabic",   font=("Segoe UI", 18), foreground=C['gold'], justify='left', lmargin1=15, lmargin2=15, spacing1=4, spacing3=4)
        t.tag_configure("pos",      font=("Segoe UI", 13, "bold"), foreground=C['mauve'], spacing1=10, spacing3=4)
        t.tag_configure("defnum",   font=("Segoe UI", sz), foreground=C['subtext'])
        t.tag_configure("defn",     font=("Segoe UI", sz), foreground=C['text'], lmargin1=25, lmargin2=25)
        t.tag_configure("eg_inline", font=("Segoe UI", sz-2, "italic"), foreground=C['subtext'], lmargin1=40, lmargin2=40)
        t.tag_configure("sec",      font=("Segoe UI", 12, "bold"), foreground=C['teal'], spacing1=8, spacing3=4, lmargin1=25)
        t.tag_configure("syn",      font=("Segoe UI", 13), foreground=C['green'], lmargin1=45, lmargin2=45)
        t.tag_configure("ant",      font=("Segoe UI", 13), foreground=C['peach'], lmargin1=45, lmargin2=45)
        t.tag_configure("longdef",  font=("Segoe UI", sz-1), foreground=C['text'], lmargin1=25, lmargin2=25)
        t.tag_configure("ctx",      font=("Segoe UI", sz-1), foreground=C['text'], lmargin1=40, lmargin2=40, spacing1=3, spacing3=3)
        t.tag_configure("bullet",   font=("Segoe UI", sz-1), foreground=C['teal'], lmargin1=25)
        t.tag_configure("div",      foreground=C['overlay'], font=("Segoe UI", 6), spacing1=8, spacing3=8, justify='center')
        t.tag_configure("err",      font=("Segoe UI", sz), foreground=C['red'], spacing1=10)
        t.tag_configure("nores",    font=("Segoe UI", sz), foreground=C['subtext'], lmargin1=25, spacing1=5)
        t.tag_configure("highlight", underline=True)

    # --- Window management ---
    def show_input_window(self):
        self.hide_result_window()
        self._loading = False
        self.input_label.config(text="Look up a word", fg=C['blue'])
        self.status_label.config(text="Press Enter to search", fg=C['subtext'])
        self.entry.config(state=tk.NORMAL)
        self.entry.delete(0, tk.END)
        self._refresh_history()
        self._show_window(self.input_window)
        self.input_window.after(50, lambda: (self.entry.focus_force(), self.entry.focus_set()))

    def clipboard_lookup(self):
        """Grab clipboard text and look it up."""
        try:
            text = self.root.clipboard_get().strip()
            if text and len(text.split()) <= 3:
                self.hide_result_window()
                self._loading = False
                self.entry.config(state=tk.NORMAL)
                self.entry.delete(0, tk.END)
                self.entry.insert(0, text)
                self._refresh_history()
                self._show_window(self.input_window)
                self.input_window.after(100, self.start_lookup)
                return
        except tk.TclError:
            pass
        self.root.after(0, self.show_input_window)

    def hide_input_window(self):
        self._loading = False
        self.input_window.withdraw()

    def hide_result_window(self):
        self.result_window.withdraw()

    def _search_again(self):
        self.hide_result_window()
        self.show_input_window()

    # --- Lookup ---
    def start_lookup(self, event=None):
        word = self.entry.get().strip()
        if not word:
            return
        self.entry.config(state=tk.DISABLED)
        self._loading = True
        self.status_label.config(text="")
        self._animate(word, 0)
        threading.Thread(target=self._run_lookup, args=(word,), daemon=True).start()

    def _animate(self, word, n):
        if not self._loading:
            return
        dots = "\u00b7" * ((n % 3) + 1) + " " * (2 - n % 3)
        self.input_label.config(text=f"Searching {dots}", fg=C['lavender'])
        self.status_label.config(text=word, fg=C['subtext'])
        self.input_window.after(350, lambda: self._animate(word, n + 1))

    def _run_lookup(self, word):
        cached = self.cache.get(word.lower())
        if cached is not None:
            self.root.after(0, lambda: self._on_result(word, cached))
            return
        if not check_connectivity():
            self.root.after(0, lambda: self._show_error("No internet connection."))
            return
        try:
            data = get_word_data(word)
        except Exception as e:
            self.root.after(0, lambda: self._show_error(f"Unexpected error: {e}"))
            return
        if isinstance(data, dict) and data.get('network_error'):
            self.root.after(0, lambda: self._show_error(data.get('error', 'Network error')))
            return
        if data is None:
            self.root.after(0, lambda: self._show_error(f"No results found for '{word}'."))
            return
        self.cache[word.lower()] = data
        self.root.after(0, lambda: self._on_result(word, data))

    def _on_result(self, word, data):
        self._loading = False
        self.add_to_history(word)
        self._display(word, data)

    # --- Inline error ---
    def _show_error(self, msg):
        self._loading = False
        self.hide_input_window()
        self.result_window.title("Lookup Error")
        t = self.result_text
        t.config(state=tk.NORMAL)
        t.delete(1.0, tk.END)
        t.insert(tk.END, "\n\u26A0  " + msg + "\n", "err")
        t.config(state=tk.DISABLED)
        self._show_window(self.result_window)

    # --- Rich display (Formatted in specific requested order) ---
    def _display(self, word, data):
        self.hide_input_window()
        self._current_word = word
        self._current_data = data
        self.result_window.title(f"def \u2014 {word}")
        t = self.result_text
        t.config(state=tk.NORMAL)
        t.delete(1.0, tk.END)

        # 1. Title + Phonetic
        t.insert(tk.END, word, "title")
        if data.get('phonetic'):
            t.insert(tk.END, f"  {data['phonetic']}", "ipa")
        t.insert(tk.END, "\n")
        # Mark end of title line — underline search starts AFTER this
        title_end = t.index(tk.INSERT)
        t.insert(tk.END, "\u2501" * 60 + "\n", "div")

        # 2. Arabic Translations (from Reverso)
        if data.get('ar_words'):
            for ar_word in data['ar_words'][:8]:
                t.insert(tk.END, get_display(arabic_reshaper.reshape(ar_word)) + "   ", "arabic")
            t.insert(tk.END, "\n")
        else:
            t.insert(tk.END, "No Arabic translations found.\n", "nores")
        
        t.insert(tk.END, "\u2501" * 60 + "\n", "div")

        # 3. Short Definition (Prioritizes Vocab.com)
        if data.get('short_def'):
            t.insert(tk.END, data['short_def'] + "\n", "defn")
        else:
            t.insert(tk.END, "No short definition found.\n", "nores")

        t.insert(tk.END, "\u2501" * 60 + "\n", "div")

        # 4. Long Definition (From Vocab.com)
        if data.get('long_def'):
            t.insert(tk.END, data['long_def'] + "\n", "longdef")
        else:
            t.insert(tk.END, "No long definition found.\n", "nores")

        t.insert(tk.END, "\u2501" * 60 + "\n", "div")

        # 5. English Examples (from Reverso)
        if data.get('eng_examples'):
            for s in data['eng_examples'][:5]:
                t.insert(tk.END, "\u2022 ", "bullet")
                t.insert(tk.END, s + "\n\n", "ctx")
        else:
            t.insert(tk.END, "No English examples found.\n", "nores")

        # 6. Additional Extracted Data (Grammar, Synonyms, Antonyms)
        if data.get('meanings'):
            t.insert(tk.END, "\u2501" * 60 + "\n", "div")
            t.insert(tk.END, "  ADDITIONAL DETAILS\n", "pos")
            for m in data['meanings']:
                if m.get('pos'):
                    t.insert(tk.END, f"\n  {m['pos'].upper()}\n", "pos")
                for i, d in enumerate(m.get('definitions', []), 1):
                    t.insert(tk.END, f"  {i}. ", "defnum")
                    t.insert(tk.END, d['text'] + "\n", "defn")
                    if d.get('example'):
                        t.insert(tk.END, f'     \"{d["example"]}\"\n', "eg_inline")
                if m.get('synonyms'):
                    t.insert(tk.END, "\n  Synonyms:\n", "sec")
                    t.insert(tk.END, " \u2022 " + ", ".join(m['synonyms']) + "\n", "syn")
                if m.get('antonyms'):
                    t.insert(tk.END, "\n  Antonyms:\n", "sec")
                    t.insert(tk.END, " \u2022 " + ", ".join(m['antonyms']) + "\n", "ant")

        t.config(state=tk.DISABLED)
        # Underline every occurrence of the word after the title line
        self._highlight_word(word, title_end)
        self._show_window(self.result_window)

    def _highlight_word(self, word, start_index):
        """Underline every case-insensitive occurrence of `word` starting after `start_index`."""
        t = self.result_text
        t.tag_remove("highlight", "1.0", tk.END)
        if not word:
            return
        search_word = word.lower()
        search_start = start_index
        while True:
            pos = t.search(search_word, search_start, tk.END, nocase=True)
            if not pos:
                break
            end_pos = f"{pos}+{len(word)}c"
            t.tag_add("highlight", pos, end_pos)
            search_start = end_pos

    # --- Copy ---
    def _copy(self):
        """Copy the full result text to clipboard."""
        try:
            txt = self.result_text.get(1.0, tk.END).strip()
            self.root.clipboard_clear()
            self.root.clipboard_append(txt)
            self.copy_btn.config(text="\u2713 Copied!")
            self.result_window.after(1500, lambda: self.copy_btn.config(text="\U0001F4CB Copy All"))
        except Exception:
            pass

    def _copy_smart(self):
        """Copy word + Arabic translations + two Vocabulary.com definitions."""
        try:
            word = self._current_word
            data = self._current_data
            lines = [word]
            # Arabic translations
            if data.get('ar_words'):
                ar_list = data['ar_words'][:8]
                lines.append("Arabic: " + " | ".join(ar_list))
            # Two vocab.com definitions (short + long)
            if data.get('short_def'):
                lines.append("Def 1: " + data['short_def'])
            if data.get('long_def'):
                lines.append("Def 2: " + data['long_def'])
            text = "\n".join(lines)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.smart_copy_btn.config(text="\u2713 Copied!")
            self.result_window.after(1500, lambda: self.smart_copy_btn.config(text="\U0001F4CB Copy"))
        except Exception:
            pass

    # --- Zoom ---
    def _zoom(self, event=None, d=0):
        if event and hasattr(event, 'delta') and event.delta:
            d = 1 if event.delta > 0 else -1
        new = max(8, min(72, self.app_font.cget("size") + d * 2))
        self.app_font.configure(size=new)
        self.zoom_label.config(text=f"{int(new / self.base_font_size * 100)}%")

    # --- Tray icon ---
    def create_tray_icon(self):
        img = Image.new('RGB', (64, 64), color=(30, 144, 255))
        try:
            draw = ImageDraw.Draw(img)
            draw.text((15, 10), "W", fill=(255, 255, 255),
                      font=ImageFont.truetype("arial.ttf", 40))
        except Exception:
            pass
        for name in ["app.png", "tray_icon.png", "app.ico"]:
            try:
                p = resource_path(name)
                if os.path.exists(p):
                    img = Image.open(p)
                    break
            except Exception:
                pass
        menu = pystray.Menu(
            pystray.MenuItem('Show', lambda: self.root.after(0, self.show_input_window)),
            pystray.MenuItem('Customize Shortcuts', lambda: self.root.after(0, self._open_shortcut_win)),
            pystray.MenuItem('Exit', self._tray_exit),
        )
        self.tray_icon = pystray.Icon(APP_NAME, img, APP_NAME, menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    # --- Shortcut customization ---
    def _open_shortcut_win(self):
        win = Toplevel(self.root)
        win.title("Customize Shortcuts")
        win.configure(bg=C['bg'])
        win.resizable(False, False)
        self._center(win, 420, 320)

        ls = dict(font=("Segoe UI", 12), bg=C['bg'], fg=C['text'])
        es = dict(
            font=("Segoe UI", 13), justify='center',
            bg=C['surface'], fg=C['text'], insertbackground=C['text'],
            selectbackground=C['blue'], selectforeground=C['bg'],
            relief=tk.FLAT, bd=6,
        )

        Label(win, text="Search Hotkey", font=("Segoe UI", 14, "bold"),
              bg=C['bg'], fg=C['blue']).pack(pady=(15, 2))
        Label(win, text=f"Current: {self.hotkey}", **ls).pack()
        v1 = tk.StringVar(value=self.hotkey)
        e1 = Entry(win, textvariable=v1, width=28, **es)
        e1.pack(pady=5, padx=20)

        Label(win, text="Clipboard Lookup Hotkey", font=("Segoe UI", 14, "bold"),
              bg=C['bg'], fg=C['blue']).pack(pady=(15, 2))
        Label(win, text=f"Current: {self.clip_hotkey}", **ls).pack()
        v2 = tk.StringVar(value=self.clip_hotkey)
        e2 = Entry(win, textvariable=v2, width=28, **es)
        e2.pack(pady=5, padx=20)

        def on_key(var):
            def handler(e):
                mods = []
                if e.state & 0x0004: mods.append('<ctrl>')
                if e.state & 0x20000: mods.append('<alt>')
                if e.state & 0x0001: mods.append('<shift>')
                key = e.keysym.lower()
                if key not in ('control_l', 'control_r', 'alt_l', 'alt_r', 'shift_l', 'shift_r'):
                    var.set("+".join(sorted(set(mods)) + [f'<{key}>' if len(key) > 1 else key]))
                return "break"
            return handler

        e1.bind("<KeyPress>", on_key(v1))
        e2.bind("<KeyPress>", on_key(v2))

        def save():
            if '+' in v1.get() and '+' in v2.get():
                self.clip_hotkey = v2.get()
                self.restart_hotkey_listener(v1.get())
                win.destroy()

        Button(
            win, text="Save", font=("Segoe UI", 12, "bold"),
            bg=C['blue'], fg=C['bg'], activebackground=C['lavender'],
            activeforeground=C['bg'], relief=tk.FLAT, bd=0,
            padx=20, pady=6, cursor="hand2", command=save,
        ).pack(pady=15)

        self._show_window(win)
        e1.focus_set()

    def _tray_exit(self):
        self.root.after(0, self.on_close)

    def on_close(self):
        if self.tray_icon:
            self.tray_icon.stop()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        self.root.destroy()

    # --- Hotkey management ---
    def start_hotkey_listener(self, hotkey_string):
        def on_activate():
            self.root.after(0, self.show_input_window)

        def on_clip():
            self.root.after(0, self.clipboard_lookup)

        try:
            hotkeys = {hotkey_string: on_activate}
            if self.clip_hotkey:
                hotkeys[self.clip_hotkey] = on_clip
            self.hotkey_listener = keyboard.GlobalHotKeys(hotkeys)
            self.hotkey_listener.run()
        except Exception as e:
            self.root.after(0, lambda: self._show_error(
                f"Failed to register hotkey '{hotkey_string}': {e}"))

    def restart_hotkey_listener(self, new_hotkey):
        self.hotkey = new_hotkey
        self.save_config()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        threading.Thread(target=self.start_hotkey_listener, args=(self.hotkey,),
                         daemon=True).start()


def main():
    setup_auto_start()
    root = tk.Tk()
    app = WordLookupApp(root)
    app.restart_hotkey_listener(app.hotkey)
    app.create_tray_icon()
    root.mainloop()


if __name__ == '__main__':
    main()