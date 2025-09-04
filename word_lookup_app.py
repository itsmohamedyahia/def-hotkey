# word_lookup_app.py
"""
Word Lookup App — show input window with Ctrl+Alt+W.
When Enter is pressed: input window disappears immediately.
If lookup succeeds -> show results window.
If lookup fails -> show an error dialog.
"""
import sys
import threading
import tkinter as tk
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

def highlight_word_for_gui(word, sentence_text):
    if not sentence_text:
        return ""
    try:
        highlighted = re.sub(
            rf"(\b{re.escape(word)}\b)",
            r"*\1*",
            sentence_text,
            flags=re.IGNORECASE
        )
        return highlighted
    except re.error:
        return sentence_text

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
        results['eng_examples'] = [el.get_text(strip=True) for el in eng_sents_tags if el.get_text(strip=True)]
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
                highlighted_line = highlight_word_for_gui(search_word, line)
                output_lines.append(add_padding(highlighted_line, SPACE))
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
        self.root.withdraw()
        self.input_window = None
        self.result_window = None
        self.result_text_widget = None
        self.hotkey_listener = None
        self.tray_icon = None

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def show_input_window(self):
        if self.input_window and self.input_window.winfo_exists():
            self.input_window.lift()
            self.input_window.focus_force()
            return

        self.input_window = Toplevel(self.root)
        self.input_window.title("Look Up Word")
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
        try:
            self.input_window.grab_set()
        except Exception:
            pass

        # Bind Enter to start_lookup and Escape to close
        self.entry.bind("<Return>", self.start_lookup)
        self.input_window.bind("<Escape>", lambda e: self.close_input_window())

        # Remove topmost after a short time so it doesn't permanently stay above all windows
        self.input_window.after(200, lambda: self.input_window.attributes("-topmost", False))

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
        # Called from GUI thread when user presses Enter.
        word = self.entry.get().strip()
        if not word:
            # do nothing if empty
            return
        # Close the input window immediately (user requested this)
        self.close_input_window()

        # Start background thread to fetch data; do NOT create a results window yet.
        lookup_thread = threading.Thread(target=self.run_lookup_and_update_gui, args=(word,), daemon=True)
        lookup_thread.start()

    def run_lookup_and_update_gui(self, word):
        # This runs in a background thread. Catch exceptions and report back to main thread.
        try:
            data = get_word_data(word)
        except Exception as e:
            # unexpected exception — schedule error dialog on main thread
            self.root.after(0, lambda: messagebox.showerror("Lookup error", f"An unexpected error occurred: {e}"))
            return

        # Handle explicit network error sentinel from get_word_data
        if isinstance(data, dict) and data.get('network_error'):
            err_detail = data.get('error', 'Network error')
            self.root.after(0, lambda: messagebox.showerror("Network error",
                                                            f"Could not reach the lookup services.\nPlease check your internet connection.\n\nDetails: {err_detail}"))
            return

        # If get_word_data returns None => word not found (no useful data)
        if data is None:
            self.root.after(0, lambda: messagebox.showinfo("No results", f"No results found for '{word}'."))
            return

        # Otherwise format and show results window on main thread
        formatted_results = format_data_for_display(word, data)
        self.root.after(0, lambda: self.display_results(formatted_results, f"Results for '{word}'"))

    def close_result_window(self, event=None):
        """Close the results window (safe to call even if it doesn't exist)."""
        try:
            if self.result_window and self.result_window.winfo_exists():
                self.result_window.destroy()
                self.result_window = None
                self.result_text_widget = None
        except Exception:
            pass

    def display_results(self, content, title="Results"):
        """Create a centered results window and bind Esc to close it."""
        # Destroy previous results window if present
        if self.result_window and self.result_window.winfo_exists():
            try:
                self.result_window.destroy()
            except Exception:
                pass

        self.result_window = Toplevel(self.root)
        self.result_window.title(title)
        self.result_window.attributes("-topmost", True)

        # ScrolledText widget
        self.result_text_widget = scrolledtext.ScrolledText(
            self.result_window, wrap=tk.WORD, width=80, height=25
        )
        self.result_text_widget.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        self.result_text_widget.insert(tk.INSERT, content)
        self.result_text_widget.config(state=tk.DISABLED)

        # Bind Esc to close results window
        # bind to the Toplevel so pressing Esc anywhere in the window will close it
        self.result_window.bind("<Escape>", lambda e: self.close_result_window())

        # Force layout so window has actual pixel size, then center it
        self.result_window.update_idletasks()
        win_w = self.result_window.winfo_width()
        win_h = self.result_window.winfo_height()
        screen_w = self.result_window.winfo_screenwidth()
        screen_h = self.result_window.winfo_screenheight()
        x = (screen_w // 2) - (win_w // 2)
        y = (screen_h // 2) - (win_h // 2)
        self.result_window.geometry(f"+{x}+{y}")

        # Focus and remove topmost shortly after
        self.result_window.lift()
        self.result_window.focus_force()
        self.result_window.after(200, lambda: self.result_window.attributes("-topmost", False))

    def update_result_window(self, content, word):
        """Update the existing results window's content and re-center it."""
        if self.result_window and self.result_window.winfo_exists() and self.result_text_widget:
            try:
                self.result_window.title(f"Results for '{word}'")
                self.result_text_widget.config(state=tk.NORMAL)
                self.result_text_widget.delete('1.0', tk.END)
                self.result_text_widget.insert('1.0', content)
                self.result_text_widget.config(state=tk.DISABLED)

                # Re-center the window after the content change (in case size changed)
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
            except Exception:
                pass
        else:
            # If no result window exists, create one
            self.display_results(content, f"Results for '{word}'")

    def create_tray_icon(self):
        try:
            # Create a transparent image
            img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)

            # Draw blue circle background
            d.ellipse((0, 0, 64, 64), fill=(30, 144, 255, 255))

            # Always use a font (try truetype first, fallback to default)
            try:
                f = ImageFont.truetype("arial.ttf", 32)
            except Exception:
                f = ImageFont.load_default()

            # Draw white "W" in the center
            w_text = "W"
            tw, th = d.textsize(w_text, font=f)
            d.text(((64 - tw) / 2, (64 - th) / 2), w_text, font=f, fill=(255, 255, 255, 255))

        except Exception:
            # If anything fails, fallback to plain blue square
            img = Image.new('RGB', (64, 64), color=(30, 144, 255))

        # Menu items
        menu = pystray.Menu(
            pystray.MenuItem('Show', lambda: self.root.after(0, self.show_input_window)),
            pystray.MenuItem('Exit', lambda: self.root.after(0, self.on_tray_exit()))
        )

        icon = pystray.Icon("word_lookup", img, "Word Lookup", menu)
        self.tray_icon = icon

        def run_icon():
            try:
                icon.run()
            except Exception:
                pass

        t = threading.Thread(target=run_icon, daemon=True)
        t.start()

    def on_tray_exit(self):
        def _exit():
            try:
                if self.tray_icon:
                    try:
                        self.tray_icon.stop()
                    except Exception:
                        pass
                if self.hotkey_listener:
                    try:
                        self.hotkey_listener.stop()
                    except Exception:
                        pass
                self.root.quit()
            except Exception:
                try:
                    self.root.destroy()
                except Exception:
                    pass
        return _exit

    def on_close(self):
        try:
            if self.tray_icon:
                try:
                    self.tray_icon.stop()
                except Exception:
                    pass
            if self.hotkey_listener:
                try:
                    self.hotkey_listener.stop()
                except Exception:
                    pass
        finally:
            try:
                self.root.destroy()
            except Exception:
                pass

# --- Hotkey ---
def start_app_hotkey():
    try:
        app.root.after(0, app.show_input_window)
    except Exception:
        pass

def create_and_start_hotkey_listener():
    hotkeys = {'<ctrl>+<alt>+w': start_app_hotkey}
    listener = keyboard.GlobalHotKeys(hotkeys)
    app.hotkey_listener = listener
    listener.start()
    try:
        listener.join()
    except Exception:
        pass

# --- Main ---
if __name__ == '__main__':
    root = tk.Tk()
    app = WordLookupApp(root)

    # hotkey listener
    hk_thread = threading.Thread(target=create_and_start_hotkey_listener, daemon=True)
    hk_thread.start()

    # tray icon (optional)
    try:
        app.create_tray_icon()
    except Exception:
        pass

    try:
        root.mainloop()
    finally:
        try:
            if app.hotkey_listener:
                app.hotkey_listener.stop()
        except Exception:
            pass
        try:
            if app.tray_icon:
                app.tray_icon.stop()
        except Exception:
            pass
        sys.exit(0)
