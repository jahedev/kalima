# 📖 Arabic EPUB Dictionary Reader for macOS

A macOS Arabic EPUB reader with clickable Apple Dictionary.app lookup. Save vocabulary, edit definitions and notes, highlight saved words in blue, and export your saved words to CSV or Anki HTML.

GitHub: https://github.com/jahedev/arabic-epub-dict-macos

## ✨ Features

* Open and read Arabic EPUB files
* Right-to-left Arabic reading layout
* Chapter/sidebar navigation
* Font zoom controls
* Search inside the current chapter
* Click any word to show a dictionary popup
* Optional lookup mode that opens macOS Dictionary.app
* Save vocabulary to a local SQLite database
* Edit the definition before saving
* Add optional notes to saved words
* Delete saved vocabulary entries
* Saved words are highlighted blue in the EPUB
* Reopening the same EPUB restores saved-word highlights
* Toggle between showing:

  * live Dictionary.app definition
  * your saved definition
* Export vocabulary to CSV
* Export Anki-ready HTML import file

## 🍎 macOS Dictionary Setup

Before using the app:

1. Open **Dictionary.app**
2. Go to **Dictionary > Settings** or **Preferences**
3. Enable **Arabic – English** / Oxford Arabic Dictionary if available
4. Move it higher in the list if you want it preferred

The app uses macOS Dictionary Services, so lookup results depend on the dictionaries enabled in Dictionary.app.

## 🚀 Install

Clone the repo:

```bash
git clone https://github.com/jahedev/arabic-epub-dict-macos.git
cd arabic-epub-dict-macos
```

Create and activate a virtual environment:

```bash
python3 -m venv epubdict-env
source epubdict-env/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## ▶️ Run

```bash
python arabic_epub_dictionary_reader.py
```

If your main file has a different name, run that file instead, for example:

```bash
python guiapp.py
```

## 🧑‍🏫 Basic Usage

1. Click **Open EPUB**
2. Choose an Arabic `.epub` file
3. Click any word in the text
4. View the dictionary popup
5. Click **Save word** to edit and save the definition
6. Saved words turn blue in the EPUB

## 🔎 Lookup Modes

Use the toolbar toggle:

- **Lookup: Popup** — shows the in-app popup
- **Lookup: Dictionary.app** — opens the word in macOS Dictionary.app using `dict://word`

Native macOS Force Click lookup is not reliably exposed through PyQt WebEngine, so Dictionary.app mode is the closest stable option.

## 💾 Saved Vocabulary

Saved vocabulary is stored locally in SQLite:

```bash
~/Library/Application Support/ArabicEpubDictionaryReader/vocabulary.sqlite3
```

Each saved entry stores:

* word
* normalized word
* dictionary term
* saved definition
* original dictionary definition
* optional note
* book title
* chapter title
* chapter index
* saved/updated timestamps

EPUBs are remembered using a SHA-256 hash of the file, so reopening the same EPUB restores saved highlights.

## 🔀 Definition Toggle

Use the toolbar toggle:

- **Definition: Dictionary** — shows a fresh dictionary lookup
- **Definition: Saved** — shows your edited saved definition for saved words

## 📤 Export

### CSV

Click **Export vocab CSV** to create:

```bash
~/Documents/arabic_epub_vocab.csv
```

### Anki HTML

Click **Export Anki HTML** to create:

```bash
~/Documents/arabic_epub_anki_import.txt
```

The Anki export uses:

```text
#separator:Tab
#html:true
#columns:Front	Back
```

Card format:

* **Front:** Arabic word only
* **Back:** saved definition as HTML

In Anki:

1. Go to **File > Import**
2. Choose `arabic_epub_anki_import.txt`
3. Use a Basic note type
4. Map `Front` to Front and `Back` to Back
5. Keep HTML enabled if prompted

## ⚠️ Notes

Apple’s Dictionary Services API returns plain-text dictionary output, not the full rich Dictionary.app layout. This app reformats the result to make it easier to read, but it may not look exactly like Dictionary.app.

## License

Personal project. Add your preferred license before publishing publicly.
