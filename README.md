# def (Dictionary CLI)

A high-speed, hotkey-driven command-line utility for medical professionals and students to quickly look up Arabic and English definitions and usage examples.

## 🚀 Key Features
- **Global Hotkey (Ctrl+Alt+W):** Instantly trigger a lookup window from any application.
- **Bilingual Scraper:** Aggregates data from `Reverso Context` (Arabic meanings/examples) and `Vocabulary.com` (detailed English definitions).
- **RTL Optimization:** Implements Arabic reshaping and bidi algorithms to ensure Arabic text renders correctly in the Python UI.
- **Zero-Distraction UI:** Disappears immediately once the word is submitted, keeping the focus on your primary work.

## 🧠 Development Philosophy
This project highlights my experience in **Bilingual Data Integrity**. I managed the AI's development of the scraping logic, ensuring that the semantic link between Arabic translations and English definitions remained logically sound even when dealing with complex medical terminology.

## 🛠 Tech Stack
- **Language:** Python
- **Web Scraping:** BeautifulSoup4, Cloudscraper
- **Formatting:** Arabic-Reshaper, Python-Bidi
- **Interface:** Tkinter