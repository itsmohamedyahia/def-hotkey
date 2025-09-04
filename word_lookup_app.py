# word_lookup_app.py
import sys
import threading
import tkinter as tk
from tkinter import scrolledtext, Toplevel, Entry, Label
from pynput import keyboard

# --- Your Original Imports (Keep them all) ---
import cloudscraper
import requests
from bs4 import BeautifulSoup
import textwrap
import re
import arabic_reshaper
from bidi.algorithm import get_display

# --- Configuration (from your script) ---
SPACE = 2
WRAP_WIDTH = 70

# --- Helper Functions (from your script, slightly modified for GUI) ---

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
    """Highlights the word by surrounding it with asterisks for the GUI."""
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

# --- Data Fetching Function (Your original function, unchanged) ---

def get_word_data(word):
    """
    Fetches data from Vocabulary.com and Reverso Context.
    (This is your original function, no changes needed here)
    """
    results = {
        'short_def': None,
        'long_def': None,
        'ar_words': None,
        'eng_examples': None,
        'error': None
    }
    error_messages = []
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False},
        delay=10
    )

    # Fetch from Vocabulary.com
    vocab_url = f"https://www.vocabulary.com/dictionary/{word}"
    try:
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
        error_messages.append(f"Vocabulary.com Error: {e}")

    # Fetch from Reverso Context
    reverso_url = f"https://context.reverso.net/translation/english-arabic/{word}"
    try:
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
        error_messages.append(f"Reverso Context Error: {e}")

    if error_messages:
        results['error'] = "\n".join(error_messages)

    # Check if any data was retrieved at all
    if not any(v for k, v in results.items() if k != 'error' and v):
        return None  # Return None if no useful data found

    return results

# --- NEW: Function to format results for the GUI window ---

def format_data_for_display(search_word, data):
    """Takes the data dictionary and formats it into a single string for display."""
    if data is None:
        return f"Could not find any results for '{search_word}'."

    output_lines = []
    divider = "-" * 50

    # 1. Arabic Words
    output_lines.append(divider)
    if data.get('ar_words'):
        ar_lines = x_word_per_line(data['ar_words'], 5)
        for line in ar_lines:
            reshaped_text = arabic_reshaper.reshape(line)
            bidi_text = get_display(reshaped_text)
            output_lines.append(add_padding(bidi_text, SPACE))
    else:
        output_lines.append(add_padding("No Arabic translations found.", SPACE))

    # 2. Short Definition
    output_lines.append(divider)
    if data.get('short_def'):
        short_def_lines = wrap_string(data['short_def'], WRAP_WIDTH)
        for line in short_def_lines:
            output_lines.append(add_padding(line, SPACE))
    else:
        output_lines.append(add_padding("No short definition found.", SPACE))

    # 3. Long Definition
    output_lines.append(divider)
    if data.get('long_def'):
        long_def_lines = wrap_string(data['long_def'], WRAP_WIDTH)
        for line in long_def_lines:
            output_lines.append(add_padding(line, SPACE))
    else:
        output_lines.append(add_padding("No long definition found.", SPACE))

    # 4. English Examples
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

    # Add any errors to the end
    if data.get('error'):
        output_lines.append("\nNotes / Errors:")
        output_lines.append(data['error'])

    return "\n".join(output_lines)

# --- NEW: Main Application Class ---

class WordLookupApp:
    def __init__(self, root):
        self.root = root
        self.root.withdraw()  # Hide the main window
        self.input_window = None
        self.result_window = None
        self.result_text_widget = None
        self.hotkey_listener = None

        # When closing main window, ensure listener stops
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def show_input_window(self):
        # If a window is already open, bring it to the front
        if self.input_window and self.input_window.winfo_exists():
            self.input_window.lift()
            self.input_window.focus_force()
            return

        self.input_window = Toplevel(self.root)
        self.input_window.title("Look Up Word")
        # Keep it on top initially
        self.input_window.attributes("-topmost", True)

        # Remove window decorations? (optional)
        # self.input_window.overrideredirect(True)

        # Center the window
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
        # Ensure the entry receives focus and input
        self.input_window.lift()
        self.input_window.focus_force()
        self.entry.focus_set()
        try:
            # Try to grab focus so typing goes to this Toplevel
            self.input_window.grab_set()
        except Exception:
            pass

        # Bind Enter key to the lookup function
        self.entry.bind("<Return>", self.start_lookup)
        # Bind Escape key to close the window
        self.input_window.bind("<Escape>", lambda e: self.close_input_window())

        # Once shown, remove permanent topmost (optional), keep it visible but not forced above all windows later
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
        word = self.entry.get().strip()
        if word:
            # Close input window and show a temporary results window
            self.close_input_window()
            self.display_results(f"Looking up '{word}'...", f"Results for '{word}'")

            # Run the data fetching in a separate thread to not freeze the GUI
            lookup_thread = threading.Thread(target=self.run_lookup_and_update_gui, args=(word,), daemon=True)
            lookup_thread.start()

    def run_lookup_and_update_gui(self, word):
        # This runs in a background thread
        data = get_word_data(word)
        formatted_results = format_data_for_display(word, data)

        # Schedule the GUI update to run in the main thread
        self.root.after(0, self.update_result_window, formatted_results, word)

    def display_results(self, content, title="Results"):
        if self.result_window and self.result_window.winfo_exists():
            self.result_window.destroy()

        self.result_window = Toplevel(self.root)
        self.result_window.title(title)
        # Make sure result window is on top when first created
        self.result_window.attributes("-topmost", True)
        # Add a ScrolledText and keep a reference
        self.result_text_widget = scrolledtext.ScrolledText(self.result_window, wrap=tk.WORD, width=80, height=25)
        self.result_text_widget.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        self.result_text_widget.insert(tk.INSERT, content)
        self.result_text_widget.config(state=tk.DISABLED)

        # allow the window to be focused and then return topmost to normal
        self.result_window.lift()
        self.result_window.focus_force()
        self.result_window.after(200, lambda: self.result_window.attributes("-topmost", False))

    def update_result_window(self, content, word):
        if self.result_window and self.result_window.winfo_exists() and self.result_text_widget:
            self.result_window.title(f"Results for '{word}'")
            try:
                self.result_text_widget.config(state=tk.NORMAL)
                self.result_text_widget.delete('1.0', tk.END)
                self.result_text_widget.insert('1.0', content)
                self.result_text_widget.config(state=tk.DISABLED)
                self.result_window.lift()
                self.result_window.focus_force()
            except Exception:
                pass
        else:
            # If result window doesn't exist (rare), create it
            self.display_results(content, f"Results for '{word}'")

    def on_close(self):
        # Stop hotkey listener if running and then destroy root
        try:
            if self.hotkey_listener:
                try:
                    self.hotkey_listener.stop()
                except Exception:
                    pass
            self.root.destroy()
        except Exception:
            try:
                self.root.quit()
            except Exception:
                pass


# --- Hotkey Setup using GlobalHotKeys (more reliable) ---
def start_app_hotkey():
    # Schedule the GUI call safely on the main thread
    try:
        app.root.after(0, app.show_input_window)
    except Exception:
        pass

def create_and_start_hotkey_listener():
    # Map the hotkey to the callback. Format: '<ctrl>+<alt>+w'
    hotkeys = { '<ctrl>+<alt>+w': start_app_hotkey }

    listener = keyboard.GlobalHotKeys(hotkeys)
    # Keep a reference on the app instance for shutdown
    app.hotkey_listener = listener

    listener.start()  # starts listener in its own thread
    # join() is not called here so the current thread continues (we start this function in a daemon thread)
    try:
        listener.join()
    except Exception:
        # join will block until listener stops; if the main program exits, this may raise
        pass

# --- Main Execution ---
if __name__ == "__main__":
    main_root = tk.Tk()
    app = WordLookupApp(main_root)

    # Start the hotkey listener in a background daemon thread so it won't prevent exit
    hk_thread = threading.Thread(target=create_and_start_hotkey_listener, daemon=True)
    hk_thread.start()

    # Start the Tkinter main loop
    try:
        main_root.mainloop()
    finally:
        # make sure the hotkey listener is stopped on exit
        try:
            if app.hotkey_listener:
                app.hotkey_listener.stop()
        except Exception:
            pass
        sys.exit(0)
