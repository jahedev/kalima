# Arabic EPUB Dictionary Reader

A macOS Arabic EPUB reader with clickable word lookup using Apple Dictionary.app. Save vocabulary with editable definitions and notes, highlight saved words in blue, toggle saved vs dictionary definitions, and export saved words to Anki HTML import files.

## Features

* Open and read Arabic EPUB files
* Search inside the current chapter
* Click any word to show a dictionary popup
* Optional lookup mode that opens macOS Dictionary.app
* Save vocabulary to a local SQLite database
* Edit the definition before saving
* Add optional notes to saved words
* Saved words are highlighted blue in the EPUB
* Reopening the same EPUB restores saved-word highlights
* Export vocabulary to CSV

## macOS Dictionary Setup

Before running the app, enable the Arabic dictionary in macOS:

1. Open **Dictionary.app**
2. Go to **Dictionary > Settings** or **Preferences**
3. Enable **Arabic – English** / Oxford Arabic Dictionary if available
4. Move it higher in the list if you want it preferred

The app uses macOS Dictionary Services, so dictionary results depend on the dictionaries enabled in Dictionary.app.

## Installation

### (Method 1) Easy - Paste this into Terminal App
```bash
/bin/zsh -c "$(curl -fsSL https://raw.githubusercontent.com/jahedev/kalima/refs/heads/main/install.sh)"
```



### (Method 2) Create a virtual environment:

```bash
python3 -m venv epubdict-env
source epubdict-env/bin/activate

pip install -r requirements.txt

python guiapp.py
```

## Running

```bash
python guiapp.py

# command-line lookup
python lookup.py شرح
```

## Usage

1. Click **Open EPUB**
2. Choose an Arabic `.epub` file
3. Click any word in the text
4. A popup will show the dictionary result
5. Click **Save word** to edit and save the definition
6. Saved words are highlighted in blue

## Lookup Modes

The toolbar includes a lookup mode toggle:

* **Lookup: Popup** — shows the in-app popup
* **Lookup: Dictionary.app** — opens the word in macOS Dictionary.app using `dict://word`

Native macOS Force Click lookup is not reliably exposed through PyQt WebEngine, so Dictionary.app mode is the closest stable option.

## Definition Modes

The toolbar includes a definition toggle:

* **Definition: Dictionary** — always shows the live dictionary result
* **Definition: Saved** — for saved words, shows your edited saved definition

## Vocabulary Storage

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

## Export Vocabulary CSV

Click **Export vocab CSV** to export saved vocabulary to:

```bash
~/Documents/arabic_epub_vocab.csv
```

## Export to Anki

Anki Support (in the future)

## Notes

Apple’s Dictionary Services API returns plain-text dictionary output, not the full rich Dictionary.app layout. The app reformats the result for readability, but it may not exactly match Dictionary.app.
