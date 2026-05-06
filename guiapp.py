#!/usr/bin/env python3
"""
Arabic EPUB Reader with macOS Dictionary.app popup lookup

Features
- Open and read EPUB files
- Chapter/sidebar navigation
- RTL-friendly Arabic display
- Font zoom controls
- Find-in-chapter search
- Click any word to show the macOS Dictionary Services result
- Shows surrounding sentence for the clicked word
- Shows a lightweight Arabic stem/root helper
- Save vocabulary to CSV for review or Anki import
- Uses Apple Dictionary.app dictionaries, including Oxford Arabic if enabled in Dictionary.app

macOS setup
    python3 -m venv epubdict-env
    source epubdict-env/bin/activate
    pip install PyQt6 PyQt6-WebEngine ebooklib beautifulsoup4 lxml pyobjc-framework-DictionaryServices

Run
    python arabic_epub_dictionary_reader.py

Before running, open Dictionary.app > Settings/Preferences and enable Oxford Arabic Dictionary.
Put the Oxford Arabic dictionary higher in the list if you want it to be preferred.
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, quote, unquote, urlparse

try:
    import ebooklib
    from ebooklib import epub
except ImportError as exc:
    raise SystemExit(
        "Missing EPUB dependencies. Install with:\n"
        "pip install ebooklib beautifulsoup4 lxml"
    ) from exc

try:
    from bs4 import BeautifulSoup
except ImportError as exc:
    raise SystemExit("Missing beautifulsoup4. Install with: pip install beautifulsoup4 lxml") from exc

try:
    from DictionaryServices import DCSCopyTextDefinition
except Exception:  # macOS/PyObjC only
    DCSCopyTextDefinition = None

try:
    from PyQt6.QtCore import Qt, QUrl, QSettings, QTimer, pyqtSignal
    from PyQt6.QtGui import QAction, QCursor, QGuiApplication, QKeySequence
    from PyQt6.QtWidgets import (
        QApplication,
        QFileDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QSizePolicy,
        QSplitter,
        QStatusBar,
        QTextEdit,
        QToolBar,
        QVBoxLayout,
        QWidget,
    )
    from PyQt6.QtWebEngineCore import QWebEnginePage
    from PyQt6.QtWebEngineWidgets import QWebEngineView
except ImportError as exc:
    raise SystemExit(
        "Missing PyQt6 dependencies. Install with:\n"
        "pip install PyQt6 PyQt6-WebEngine"
    ) from exc


APP_ORG = "LocalTools"
APP_NAME = "ArabicEpubDictionaryReader"

ARABIC_DIACRITICS_RE = re.compile(
    r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]"
)

TRIM_CHARS = """\ufeff\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069
\t\r\n .,;:!?()[]{}<>\"'“”‘’،؛؟«»…ـ"""

VOCAB_CSV_PATH = Path.home() / "Documents" / "arabic_epub_vocab.csv"

READER_CSS = """
html, body {
    direction: rtl;
    text-align: right;
    font-family: -apple-system, BlinkMacSystemFont, "Geeza Pro", "Arial", "Times New Roman", serif;
    font-size: 21px;
    line-height: 1.9;
    margin: 0;
    padding: 24px 38px;
    background: #fffdf8;
    color: #1f1f1f;
}
p, div, li, blockquote {
    line-height: 1.9;
}
a {
    color: inherit;
    text-decoration: underline;
}
img, svg, video {
    max-width: 100%;
    height: auto;
}
.lookup-word {
    cursor: pointer;
    border-radius: 4px;
}
.lookup-word:hover {
    background: rgba(255, 220, 120, 0.55);
}
.lookup-word-active {
    background: rgba(255, 210, 80, 0.75);
}
::selection {
    background: #ffe8a3;
}
"""

WORD_AT_POINT_JS = r"""
(function() {
    const x = __X__;
    const y = __Y__;

    function clean(s) {
        if (!s) return "";
        return s
            .replace(/[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]/g, "")
            .replace(/^[\s.,;:!?()\[\]{}<>"'“”‘’،؛؟«»…ـ]+/g, "")
            .replace(/[\s.,;:!?()\[\]{}<>"'“”‘’،؛؟«»…ـ]+$/g, "")
            .trim();
    }

    function sentenceAroundNode(node) {
        let container = node;
        while (container && container !== document.body) {
            const name = container.nodeName;
            if (["P", "DIV", "LI", "BLOCKQUOTE", "SECTION", "ARTICLE", "TD"].includes(name)) break;
            container = container.parentNode;
        }
        const text = clean((container || document.body).innerText || "");
        if (!text) return "";
        const sentences = text.split(/(?<=[\.\!\?؟؛،])\s+|\n+/).map(clean).filter(Boolean);
        if (!sentences.length) return text.slice(0, 450);
        const chosen = sentences.find(s => s.includes(clean(node.textContent || ""))) || sentences[0];
        return chosen.slice(0, 650);
    }

    const selection = window.getSelection ? window.getSelection().toString().trim() : "";
    if (selection && selection.length <= 80) {
        return {word: clean(selection.split(/\s+/)[0]), sentence: ""};
    }

    const el = document.elementFromPoint(x, y);
    if (el && el.closest) {
        const span = el.closest(".lookup-word");
        if (span && span.dataset && span.dataset.word) {
            return {word: clean(span.dataset.word), sentence: sentenceAroundNode(span)};
        }
    }

    return {word: "", sentence: ""};
})();
"""

INSTALL_WORD_LOOKUP_JS = r"""
(function() {
    if (window.__arabicReaderLookupInstalled) return "already-installed";
    window.__arabicReaderLookupInstalled = true;

    const wordRe = /([\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFFA-Za-zÀ-ÖØ-öø-ÿ0-9’'\-]+)/g;
    const skipTags = new Set(["SCRIPT", "STYLE", "TEXTAREA", "INPUT", "SELECT", "OPTION", "CODE", "PRE"]);

    function clean(s) {
        if (!s) return "";
        return s
            .replace(/[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]/g, "")
            .replace(/^[\s.,;:!?()\[\]{}<>"'“”‘’،؛؟«»…ـ]+/g, "")
            .replace(/[\s.,;:!?()\[\]{}<>"'“”‘’،؛؟«»…ـ]+$/g, "")
            .replace(/\s+/g, " ")
            .trim();
    }

    function sentenceAroundElement(el) {
        let container = el;
        while (container && container !== document.body) {
            const name = container.nodeName;
            if (["P", "DIV", "LI", "BLOCKQUOTE", "SECTION", "ARTICLE", "TD"].includes(name)) break;
            container = container.parentNode;
        }
        const blockText = clean((container || document.body).innerText || "");
        const word = clean(el.dataset.word || el.textContent || "");
        if (!blockText) return "";

        const sentences = blockText
            .split(/(?<=[\.\!\?؟؛])\s+|\n+/)
            .map(clean)
            .filter(Boolean);

        let chosen = "";
        for (const sentence of sentences) {
            if (sentence.includes(word)) {
                chosen = sentence;
                break;
            }
        }

        if (!chosen) {
            const idx = blockText.indexOf(word);
            if (idx >= 0) {
                const start = Math.max(0, idx - 220);
                const end = Math.min(blockText.length, idx + word.length + 220);
                chosen = blockText.slice(start, end);
            } else {
                chosen = blockText.slice(0, 450);
            }
        }
        return chosen.slice(0, 700);
    }

    function shouldSkip(node) {
        const parent = node.parentNode;
        if (!parent) return true;
        if (parent.classList && parent.classList.contains("lookup-word")) return true;
        if (skipTags.has(parent.nodeName)) return true;
        return false;
    }

    function wrapTextNode(textNode) {
        if (shouldSkip(textNode)) return;
        const text = textNode.nodeValue;
        if (!text || !wordRe.test(text)) return;
        wordRe.lastIndex = 0;

        const frag = document.createDocumentFragment();
        let lastIndex = 0;
        let match;
        while ((match = wordRe.exec(text)) !== null) {
            const raw = match[0];
            const start = match.index;
            if (start > lastIndex) {
                frag.appendChild(document.createTextNode(text.slice(lastIndex, start)));
            }
            const span = document.createElement("span");
            span.className = "lookup-word";
            span.dataset.word = clean(raw);
            span.textContent = raw;
            frag.appendChild(span);
            lastIndex = start + raw.length;
        }
        if (lastIndex < text.length) {
            frag.appendChild(document.createTextNode(text.slice(lastIndex)));
        }
        textNode.parentNode.replaceChild(frag, textNode);
    }

    const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(wrapTextNode);

    document.addEventListener("click", function(e) {
        const el = e.target && e.target.closest ? e.target.closest(".lookup-word") : null;
        if (!el) return;
        const word = clean(el.dataset.word || el.textContent || "");
        if (!word) return;
        const sentence = sentenceAroundElement(el);

        document.querySelectorAll(".lookup-word-active").forEach(function(x) {
            x.classList.remove("lookup-word-active");
        });
        el.classList.add("lookup-word-active");

        e.preventDefault();
        e.stopPropagation();
        window.location.href = "lookup://word?value=" + encodeURIComponent(word) + "&sentence=" + encodeURIComponent(sentence);
    }, true);

    return "installed";
})();
"""


@dataclass
class Chapter:
    idref: str
    title: str
    item_name: str
    file_path: Path


@dataclass
class ArabicAnalysis:
    normalized: str
    stem: str
    likely_root: str
    pattern: str
    notes: str


@dataclass
class LookupRecord:
    clicked_word: str = ""
    term_used: str = ""
    definition: str = ""
    sentence: str = ""
    analysis: Optional[ArabicAnalysis] = None
    book: str = ""
    chapter: str = ""


def safe_output_path(base_dir: Path, item_name: str) -> Path:
    """Prevent path traversal when extracting EPUB resources."""
    clean_name = item_name.replace("\\", "/").lstrip("/")
    target = (base_dir / clean_name).resolve()
    base = base_dir.resolve()
    if base != target and base not in target.parents:
        fallback = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(item_name).name or "epub_item")
        target = base / fallback
    return target


def clean_lookup_word(word: str) -> str:
    word = (word or "").strip(TRIM_CHARS)
    word = word.replace("\u0640", "")  # tatweel
    word = re.sub(r"\s+", " ", word)
    return word.strip(TRIM_CHARS)


def normalize_arabic(word: str) -> str:
    word = clean_lookup_word(word)
    word = ARABIC_DIACRITICS_RE.sub("", word)
    word = word.replace("ـ", "")
    word = word.replace("ٱ", "ا").replace("آ", "ا").replace("أ", "ا").replace("إ", "ا")
    word = word.replace("ى", "ي")
    return word


def lookup_variants(word: str) -> list[str]:
    """Try conservative variants. Dictionary.app is often lemma-sensitive."""
    word = clean_lookup_word(word)
    no_diacritics = ARABIC_DIACRITICS_RE.sub("", word)
    normalized_alef = (
        no_diacritics.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ٱ", "ا")
    )

    variants: list[str] = []
    for candidate in (word, no_diacritics, normalized_alef):
        candidate = clean_lookup_word(candidate)
        if candidate and candidate not in variants:
            variants.append(candidate)
    return variants


def dictionary_lookup(word: str) -> tuple[str, str]:
    """
    Returns (term_used, definition). Uses Apple Dictionary Services.
    DCSCopyTextDefinition searches the active Dictionary.app dictionaries.
    """
    if DCSCopyTextDefinition is None:
        return word, (
            "Dictionary Services is unavailable.\n\n"
            "This app must run on macOS with:\n"
            "pip install pyobjc-framework-DictionaryServices"
        )

    for term in lookup_variants(word):
        try:
            result = DCSCopyTextDefinition(None, term, (0, len(term)))
        except Exception as exc:
            return term, f"Dictionary lookup failed:\n{exc}"
        if result:
            return term, str(result)

    return word, "No definition found in the active macOS dictionaries."


def likely_arabic_analysis(word: str) -> ArabicAnalysis:
    """
    Lightweight Arabic helper, not a full morphological analyzer.
    It gives a useful study hint: normalized form, rough stem, and possible root.
    """
    normalized = normalize_arabic(word)
    stem = normalized
    notes: list[str] = []
    pattern = "heuristic"

    # Remove common clitics/prefixes conservatively.
    prefixes = [
        "وال", "فال", "بال", "كال", "لل", "ال",
        "و", "ف", "ب", "ك", "ل", "س",
        "يت", "تت", "است", "مست", "نست",
    ]
    suffixes = [
        "كما", "هما", "كن", "كم", "ها", "هم", "هن", "نا", "ني", "ي", "ه",
        "تين", "تان", "ون", "ين", "ات", "ان", "ة", "ا",
    ]

    for prefix in sorted(prefixes, key=len, reverse=True):
        if stem.startswith(prefix) and len(stem) - len(prefix) >= 3:
            stem = stem[len(prefix):]
            notes.append(f"removed prefix: {prefix}")
            break

    for suffix in sorted(suffixes, key=len, reverse=True):
        if stem.endswith(suffix) and len(stem) - len(suffix) >= 3:
            stem = stem[: -len(suffix)]
            notes.append(f"removed suffix: {suffix}")
            break

    # Handle common derived forms/patterns.
    root = ""
    s = stem

    if normalized.startswith("است") and len(normalized) >= 6:
        core = normalized[3:]
        if len(core) >= 3:
            root = core[:3]
            pattern = "استفعل / استفعال hint"
            notes.append("recognized possible استفعل/استفعال pattern")
    elif s.startswith("م") and len(s) >= 4:
        core = s[1:]
        if len(core) >= 3:
            root = core[:3]
            pattern = "مفعل / مفعول hint"
            notes.append("initial م may be part of a derived noun/participle")
    elif len(s) >= 5 and s[1] == "ا":
        # فاعل / مفاعل style clue: keep first, third, fourth letters when possible.
        root = s[0] + s[2] + s[3]
        pattern = "فاعل / related hint"
        notes.append("ا after first letter may indicate a derived pattern")
    elif len(s) >= 5 and s.startswith("ت"):
        root = s[1:4]
        pattern = "تفعّل / تفاعل hint"
        notes.append("initial ت may indicate a derived verb form")
    elif len(s) >= 4 and s[1] in {"و", "ا", "ي"}:
        root = s[0] + s[2] + s[3]
        pattern = "hollow/derived hint"
        notes.append("middle weak letter may not be part of the root")
    else:
        arabic_letters = [ch for ch in s if "\u0600" <= ch <= "\u06FF"]
        root = "".join(arabic_letters[:3])
        pattern = "first-three-letter hint"

    likely_root = " ".join(root[:3]) if root else "—"
    if not notes:
        notes.append("rough estimate only")
    notes.append("not a full Sarf analyzer; verify with dictionary/context")

    return ArabicAnalysis(
        normalized=normalized or word,
        stem=stem or normalized or word,
        likely_root=likely_root,
        pattern=pattern,
        notes="; ".join(notes),
    )


def format_dictionary_definition_html(term: str, definition: str) -> str:
    """
    Apple Dictionary Services returns plain text, not the rich layout used by Dictionary.app.
    This adds readable line breaks and simple HTML formatting.
    """
    raw = (definition or "").strip()
    if not raw:
        raw = "No definition found in the active macOS dictionaries."

    nl = chr(10)
    text = " ".join(raw.split())

    # Dictionary.app entries often contain triangle bullets for subentries/examples.
    text = text.replace("▸", nl + "    ▸ ")

    # Put numbered senses on separate lines.
    for number in range(1, 30):
        text = text.replace(" " + str(number) + " ", nl + str(number) + " ")

    # Put common parts of speech on separate lines.
    for pos in ["noun", "verb", "adjective", "adverb", "plural", "preposition", "conjunction", "interjection"]:
        text = text.replace(" " + pos + " ", nl + pos + " ")

    parts = [line.rstrip() for line in text.split(nl) if line.strip()]
    if not parts:
        parts = [text]

    html_lines: list[str] = []
    for i, line in enumerate(parts):
        escaped = html.escape(line)
        if i == 0:
            escaped = escaped.replace(" | ", " <span style='color:#777'>|</span> ")
            html_lines.append("<div class='entry-head'>" + escaped + "</div>")
        elif line.lstrip().startswith("▸"):
            html_lines.append("<div class='subentry'>" + escaped + "</div>")
        elif line.strip() and line.strip()[0].isdigit():
            html_lines.append("<div class='sense'>" + escaped + "</div>")
        elif line.lower().split(" ", 1)[0] in ["noun", "verb", "adjective", "adverb", "plural", "preposition", "conjunction", "interjection"]:
            html_lines.append("<div class='pos'>" + escaped + "</div>")
        else:
            html_lines.append("<div>" + escaped + "</div>")

    return """
    <html>
    <head>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Geeza Pro', 'Arial', sans-serif;
            font-size: 18px;
            line-height: 1.45;
            margin: 0;
            padding: 4px;
            color: #111;
            background: #fff;
        }
        .entry-head {
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 10px;
            direction: rtl;
            unicode-bidi: plaintext;
        }
        .pos {
            font-weight: 700;
            color: #444;
            margin-top: 8px;
            margin-bottom: 4px;
            direction: ltr;
            unicode-bidi: plaintext;
        }
        .sense {
            margin-top: 8px;
            margin-bottom: 4px;
            font-weight: 600;
            direction: rtl;
            unicode-bidi: plaintext;
        }
        .subentry {
            margin-right: 22px;
            margin-top: 4px;
            direction: rtl;
            unicode-bidi: plaintext;
        }
        div {
            white-space: normal;
            overflow-wrap: anywhere;
        }
    </style>
    </head>
    <body>""" + "".join(html_lines) + """</body>
    </html>
    """


def format_full_lookup_html(record: LookupRecord) -> str:
    analysis = record.analysis or likely_arabic_analysis(record.clicked_word)
    sentence = html.escape(record.sentence or "No sentence context captured.")
    word = html.escape(record.clicked_word)
    term = html.escape(record.term_used or record.clicked_word)
    root = html.escape(analysis.likely_root)
    normalized = html.escape(analysis.normalized)
    stem = html.escape(analysis.stem)
    pattern = html.escape(analysis.pattern)
    notes = html.escape(analysis.notes)
    definition_html = format_dictionary_definition_html(record.term_used, record.definition)

    # Extract only the body from the definition HTML so it can be embedded.
    match = re.search(r"<body>(.*)</body>", definition_html, flags=re.DOTALL)
    definition_body = match.group(1) if match else html.escape(record.definition)

    return f"""
    <html>
    <head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Geeza Pro', 'Arial', sans-serif;
            font-size: 16px;
            line-height: 1.45;
            margin: 0;
            padding: 4px;
            color: #111;
            background: #fff;
        }}
        .section {{
            border-bottom: 1px solid #ddd;
            padding-bottom: 10px;
            margin-bottom: 12px;
        }}
        .label {{
            font-weight: 700;
            color: #555;
            margin-bottom: 4px;
            direction: ltr;
        }}
        .word {{
            font-size: 24px;
            font-weight: 800;
            direction: rtl;
            unicode-bidi: plaintext;
        }}
        .sentence {{
            direction: rtl;
            unicode-bidi: plaintext;
            background: #fff8dc;
            border: 1px solid #ead99a;
            border-radius: 8px;
            padding: 8px;
            font-size: 18px;
        }}
        .analysis-grid {{
            display: grid;
            grid-template-columns: 115px 1fr;
            gap: 4px 10px;
        }}
        .analysis-key {{
            color: #666;
            font-weight: 700;
        }}
        .analysis-value {{
            direction: rtl;
            unicode-bidi: plaintext;
        }}
        .entry-head {{
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 10px;
            direction: rtl;
            unicode-bidi: plaintext;
        }}
        .pos {{
            font-weight: 700;
            color: #444;
            margin-top: 8px;
            margin-bottom: 4px;
            direction: ltr;
            unicode-bidi: plaintext;
        }}
        .sense {{
            margin-top: 8px;
            margin-bottom: 4px;
            font-weight: 600;
            direction: rtl;
            unicode-bidi: plaintext;
        }}
        .subentry {{
            margin-right: 22px;
            margin-top: 4px;
            direction: rtl;
            unicode-bidi: plaintext;
        }}
        div {{
            white-space: normal;
            overflow-wrap: anywhere;
        }}
    </style>
    </head>
    <body>
        <div class="section">
            <div class="label">Word</div>
            <div class="word">{word}</div>
            <div style="color:#777; margin-top:4px;">Dictionary term: {term}</div>
        </div>
        <div class="section">
            <div class="label">Sentence context</div>
            <div class="sentence">{sentence}</div>
        </div>
        <div class="section">
            <div class="label">Arabic root/stem helper</div>
            <div class="analysis-grid">
                <div class="analysis-key">Root hint</div><div class="analysis-value">{root}</div>
                <div class="analysis-key">Stem hint</div><div class="analysis-value">{stem}</div>
                <div class="analysis-key">Normalized</div><div class="analysis-value">{normalized}</div>
                <div class="analysis-key">Pattern</div><div class="analysis-value">{pattern}</div>
                <div class="analysis-key">Notes</div><div>{notes}</div>
            </div>
        </div>
        <div class="section">
            <div class="label">Dictionary</div>
            {definition_body}
        </div>
    </body>
    </html>
    """


class EpubBook:
    def __init__(self) -> None:
        self.path: Optional[Path] = None
        self.tempdir: Optional[tempfile.TemporaryDirectory[str]] = None
        self.chapters: list[Chapter] = []

    def close(self) -> None:
        self.chapters = []
        self.path = None
        if self.tempdir is not None:
            self.tempdir.cleanup()
            self.tempdir = None

    def open(self, epub_path: str | os.PathLike[str]) -> None:
        self.close()
        self.path = Path(epub_path)
        self.tempdir = tempfile.TemporaryDirectory(prefix="arabic_epub_reader_")
        out_dir = Path(self.tempdir.name)

        book = epub.read_epub(str(self.path))

        # Extract every EPUB item so chapter HTML can load local images/CSS/resources.
        for item in book.get_items():
            name = item.get_name() or f"item_{id(item)}"
            target = safe_output_path(out_dir, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            content = item.get_content()
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                content = self._prepare_html(content)
            target.write_bytes(content)

        document_items_by_id = {
            item.get_id(): item
            for item in book.get_items()
            if item.get_type() == ebooklib.ITEM_DOCUMENT
        }

        chapters: list[Chapter] = []
        for spine_entry in book.spine:
            idref = spine_entry[0] if isinstance(spine_entry, (tuple, list)) else spine_entry
            item = document_items_by_id.get(idref)
            if not item:
                continue
            title = self._extract_title(item.get_content(), item.get_name())
            chapters.append(
                Chapter(
                    idref=idref,
                    title=title,
                    item_name=item.get_name(),
                    file_path=safe_output_path(out_dir, item.get_name()),
                )
            )

        # Fallback for malformed EPUBs without a useful spine.
        if not chapters:
            for item in document_items_by_id.values():
                title = self._extract_title(item.get_content(), item.get_name())
                chapters.append(
                    Chapter(
                        idref=item.get_id(),
                        title=title,
                        item_name=item.get_name(),
                        file_path=safe_output_path(out_dir, item.get_name()),
                    )
                )

        if not chapters:
            raise ValueError("No readable HTML/XHTML chapters were found in this EPUB.")

        self.chapters = chapters

    def _prepare_html(self, content: bytes) -> bytes:
        try:
            soup = BeautifulSoup(content, "lxml")
        except Exception:
            soup = BeautifulSoup(content, "html.parser")

        if soup.html is None:
            html_tag = soup.new_tag("html")
            body_tag = soup.new_tag("body")
            body_tag.append(soup)
            html_tag.append(body_tag)
            soup = BeautifulSoup(str(html_tag), "html.parser")

        if soup.head is None:
            head = soup.new_tag("head")
            soup.html.insert(0, head)

        meta = soup.new_tag("meta")
        meta.attrs["charset"] = "utf-8"
        soup.head.insert(0, meta)

        style = soup.new_tag("style")
        style.attrs["id"] = "arabic-reader-style"
        style.string = READER_CSS
        soup.head.append(style)

        if soup.body is not None:
            existing_class = soup.body.get("class", [])
            if isinstance(existing_class, str):
                existing_class = [existing_class]
            soup.body["class"] = existing_class + ["arabic-reader-body"]
            soup.body["dir"] = "rtl"

        return str(soup).encode("utf-8")

    def _extract_title(self, content: bytes, fallback: str) -> str:
        try:
            soup = BeautifulSoup(content, "lxml")
        except Exception:
            soup = BeautifulSoup(content, "html.parser")

        for selector in ("h1", "h2", "title"):
            tag = soup.find(selector)
            if tag:
                text = " ".join(tag.get_text(" ", strip=True).split())
                if text:
                    return text[:80]
        return Path(fallback).stem.replace("_", " ")[:80] or "Chapter"


class ReaderPage(QWebEnginePage):
    chapterNavigationRequested = pyqtSignal(str)
    wordLookupRequested = pyqtSignal(str, str)

    def acceptNavigationRequest(self, url: QUrl, nav_type: QWebEnginePage.NavigationType, is_main_frame: bool) -> bool:
        if url.scheme() == "lookup":
            parsed = urlparse(url.toString())
            qs = parse_qs(parsed.query)
            query_value = qs.get("value", [""])[0]
            query_sentence = qs.get("sentence", [""])[0]
            word = clean_lookup_word(unquote(query_value))
            sentence = clean_lookup_word(unquote(query_sentence))
            if word:
                self.wordLookupRequested.emit(word, sentence)
            return False

        if nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked and url.isLocalFile():
            self.chapterNavigationRequested.emit(url.toLocalFile())
            return True
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class ReaderView(QWebEngineView):
    wordClicked = pyqtSignal(str, str)

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt method name
        super().mouseReleaseEvent(event)
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            return

        pos = event.position()
        QTimer.singleShot(80, lambda: self._lookup_at_position(int(pos.x()), int(pos.y())))

    def mouseDoubleClickEvent(self, event):  # noqa: N802 - Qt method name
        super().mouseDoubleClickEvent(event)
        if event.button() != Qt.MouseButton.LeftButton:
            return
        QTimer.singleShot(120, self._lookup_selected_text)

    def _lookup_selected_text(self) -> None:
        selected = clean_lookup_word(self.page().selectedText())
        if selected:
            self.wordClicked.emit(selected.split()[0], "")

    def _lookup_at_position(self, x: int, y: int) -> None:
        js = WORD_AT_POINT_JS.replace("__X__", str(x)).replace("__Y__", str(y))
        self.page().runJavaScript(js, self._emit_word_if_any)

    def _emit_word_if_any(self, payload: object) -> None:
        word = ""
        sentence = ""
        if isinstance(payload, dict):
            word = clean_lookup_word(str(payload.get("word", "")))
            sentence = clean_lookup_word(str(payload.get("sentence", "")))
        elif isinstance(payload, str):
            word = clean_lookup_word(payload)
        if word:
            self.wordClicked.emit(word, sentence)


class LookupPopup(QFrame):
    saveRequested = pyqtSignal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(500)
        self.setMaximumWidth(820)
        self.setMinimumHeight(320)
        self.setMaximumHeight(640)

        self.title = QLabel()
        self.title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.title.setStyleSheet("font-weight: 700; font-size: 16px;")

        self.definition = QTextEdit()
        self.definition.setReadOnly(True)
        self.definition.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.definition.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.definition.setStyleSheet("font-size: 16px; line-height: 1.5;")

        self.save_btn = QPushButton("Save word")
        self.save_btn.clicked.connect(self._emit_save)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)

        open_dictionary_btn = QPushButton("Open in Dictionary.app")
        open_dictionary_btn.clicked.connect(self.open_in_dictionary_app)

        button_row = QHBoxLayout()
        button_row.addWidget(open_dictionary_btn)
        button_row.addWidget(self.save_btn)
        button_row.addStretch(1)
        button_row.addWidget(close_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.definition)
        layout.addLayout(button_row)

        self._current_word = ""
        self._current_record: Optional[LookupRecord] = None

    def show_lookup(self, record: LookupRecord) -> None:
        self._current_record = record
        clicked_word = record.clicked_word
        term_used = record.term_used
        self._current_word = term_used or clicked_word
        if term_used and term_used != clicked_word:
            self.title.setText(f"{clicked_word}  →  {term_used}")
        else:
            self.title.setText(clicked_word)
        self.definition.setHtml(format_full_lookup_html(record))
        self.resize(680, 520)
        self.adjustSize()

        cursor_pos = QCursor.pos()
        desired_x = cursor_pos.x() + 14
        desired_y = cursor_pos.y() + 14

        screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
        if screen is not None:
            bounds = screen.availableGeometry()
            width = min(max(self.width(), self.minimumWidth()), self.maximumWidth())
            height = min(max(self.height(), self.minimumHeight()), self.maximumHeight())
            desired_x = max(bounds.left() + 8, min(desired_x, bounds.right() - width - 8))
            desired_y = max(bounds.top() + 8, min(desired_y, bounds.bottom() - height - 8))
            self.resize(width, height)

        self.move(desired_x, desired_y)
        self.show()
        self.raise_()
        self.activateWindow()

    def _emit_save(self) -> None:
        if self._current_record is not None:
            self.saveRequested.emit(self._current_record)

    def open_in_dictionary_app(self) -> None:
        if not self._current_word:
            return
        os.system(f"open 'dict://{quote(self._current_word)}' >/dev/null 2>&1 &")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Arabic EPUB Dictionary Reader")
        self.resize(1200, 820)

        self.settings = QSettings(APP_ORG, APP_NAME)
        self.book = EpubBook()
        self.current_chapter_index = -1
        self.zoom_factor = float(self.settings.value("zoom_factor", 1.0))
        self.lookup_mode = str(self.settings.value("lookup_mode", "popup"))  # popup | dictionary_app

        self.chapter_list = QListWidget()
        self.chapter_list.setMaximumWidth(320)
        self.chapter_list.currentRowChanged.connect(self.load_chapter)

        self.reader_page = ReaderPage(self)
        self.reader_page.chapterNavigationRequested.connect(self._sync_chapter_from_path)
        self.reader_page.wordLookupRequested.connect(self.lookup_word)

        self.reader_view = ReaderView()
        self.reader_view.setPage(self.reader_page)
        self.reader_view.setZoomFactor(self.zoom_factor)
        self.reader_view.wordClicked.connect(self.lookup_word)
        self.reader_view.loadFinished.connect(self.install_word_click_handler)

        splitter = QSplitter()
        splitter.addWidget(self.chapter_list)
        splitter.addWidget(self.reader_view)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        self.lookup_popup = LookupPopup(self)
        self.lookup_popup.saveRequested.connect(self.save_vocabulary_record)
        self.find_box = QLineEdit()
        self.find_box.setPlaceholderText("Find in chapter…")
        self.find_box.returnPressed.connect(self.find_next)

        self._build_toolbar()
        self.setStatusBar(QStatusBar())

        last_path = self.settings.value("last_epub_path", "")
        if last_path and Path(str(last_path)).exists():
            try:
                self.open_epub(str(last_path), restore_position=True)
            except Exception:
                pass

    def closeEvent(self, event):  # noqa: N802 - Qt method name
        self.settings.setValue("zoom_factor", self.zoom_factor)
        if self.book.path:
            self.settings.setValue("last_epub_path", str(self.book.path))
            self.settings.setValue(f"last_chapter::{self.book.path}", self.current_chapter_index)
        self.book.close()
        super().closeEvent(event)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_action = QAction("Open EPUB", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.choose_epub)
        toolbar.addAction(open_action)

        toolbar.addSeparator()

        prev_action = QAction("Previous", self)
        prev_action.setShortcut(QKeySequence.StandardKey.MoveToPreviousChar)
        prev_action.triggered.connect(self.previous_chapter)
        toolbar.addAction(prev_action)

        next_action = QAction("Next", self)
        next_action.setShortcut(QKeySequence.StandardKey.MoveToNextChar)
        next_action.triggered.connect(self.next_chapter)
        toolbar.addAction(next_action)

        toolbar.addSeparator()

        zoom_out_action = QAction("A−", self)
        zoom_out_action.setShortcut(QKeySequence.StandardKey.ZoomOut)
        zoom_out_action.triggered.connect(self.zoom_out)
        toolbar.addAction(zoom_out_action)

        zoom_in_action = QAction("A+", self)
        zoom_in_action.setShortcut(QKeySequence.StandardKey.ZoomIn)
        zoom_in_action.triggered.connect(self.zoom_in)
        toolbar.addAction(zoom_in_action)

        reset_zoom_action = QAction("Reset", self)
        reset_zoom_action.triggered.connect(self.reset_zoom)
        toolbar.addAction(reset_zoom_action)

        toolbar.addSeparator()
        toolbar.addWidget(QLabel("  Search: "))
        self.find_box.setMaximumWidth(260)
        self.find_box.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        toolbar.addWidget(self.find_box)

        find_next_action = QAction("Find Next", self)
        find_next_action.setShortcut(QKeySequence.StandardKey.FindNext)
        find_next_action.triggered.connect(self.find_next)
        toolbar.addAction(find_next_action)

        toolbar.addSeparator()
        self.lookup_mode_action = QAction(self._lookup_mode_label(), self)
        self.lookup_mode_action.setToolTip(
            "Toggle lookup behavior: in-app popup or macOS Dictionary.app. "
            "True macOS Force Click popover is not reliably exposed through PyQt WebEngine, "
            "so Dictionary.app mode uses dict://word."
        )
        self.lookup_mode_action.triggered.connect(self.toggle_lookup_mode)
        toolbar.addAction(self.lookup_mode_action)

        export_action = QAction("Open vocab CSV", self)
        export_action.setToolTip(f"Vocabulary is saved to {VOCAB_CSV_PATH}")
        export_action.triggered.connect(self.open_vocab_csv)
        toolbar.addAction(export_action)

    def choose_epub(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open EPUB",
            str(Path.home()),
            "EPUB files (*.epub);;All files (*)",
        )
        if path:
            self.open_epub(path, restore_position=False)

    def open_epub(self, path: str, restore_position: bool = False) -> None:
        try:
            self.book.open(path)
        except Exception as exc:
            QMessageBox.critical(self, "Could not open EPUB", str(exc))
            return

        self.chapter_list.blockSignals(True)
        self.chapter_list.clear()
        for chapter in self.book.chapters:
            self.chapter_list.addItem(chapter.title)
        self.chapter_list.blockSignals(False)

        self.setWindowTitle(f"Arabic EPUB Dictionary Reader — {Path(path).name}")
        self.settings.setValue("last_epub_path", path)

        chapter_index = 0
        if restore_position:
            saved = self.settings.value(f"last_chapter::{Path(path)}", 0)
            try:
                chapter_index = max(0, min(int(saved), len(self.book.chapters) - 1))
            except Exception:
                chapter_index = 0

        self.load_chapter(chapter_index)

    def load_chapter(self, index: int) -> None:
        if not self.book.chapters:
            return
        if index < 0 or index >= len(self.book.chapters):
            return

        self.current_chapter_index = index
        chapter = self.book.chapters[index]

        self.chapter_list.blockSignals(True)
        self.chapter_list.setCurrentRow(index)
        self.chapter_list.blockSignals(False)

        self.reader_view.load(QUrl.fromLocalFile(str(chapter.file_path)))
        self.statusBar().showMessage(
            f"Chapter {index + 1} of {len(self.book.chapters)} — single-click a word for Dictionary lookup"
        )

    def install_word_click_handler(self, ok: bool) -> None:
        if not ok:
            return
        self.reader_view.page().runJavaScript(INSTALL_WORD_LOOKUP_JS)

    def previous_chapter(self) -> None:
        self.load_chapter(self.current_chapter_index - 1)

    def next_chapter(self) -> None:
        self.load_chapter(self.current_chapter_index + 1)

    def zoom_in(self) -> None:
        self.zoom_factor = min(3.0, self.zoom_factor + 0.1)
        self.reader_view.setZoomFactor(self.zoom_factor)
        self.settings.setValue("zoom_factor", self.zoom_factor)

    def zoom_out(self) -> None:
        self.zoom_factor = max(0.5, self.zoom_factor - 0.1)
        self.reader_view.setZoomFactor(self.zoom_factor)
        self.settings.setValue("zoom_factor", self.zoom_factor)

    def reset_zoom(self) -> None:
        self.zoom_factor = 1.0
        self.reader_view.setZoomFactor(self.zoom_factor)
        self.settings.setValue("zoom_factor", self.zoom_factor)

    def find_next(self) -> None:
        text = self.find_box.text().strip()
        if text:
            self.reader_view.findText(text)

    def _lookup_mode_label(self) -> str:
        if getattr(self, "lookup_mode", "popup") == "dictionary_app":
            return "Lookup: Dictionary.app"
        return "Lookup: Popup"

    def toggle_lookup_mode(self) -> None:
        self.lookup_mode = "dictionary_app" if self.lookup_mode == "popup" else "popup"
        self.settings.setValue("lookup_mode", self.lookup_mode)
        self.lookup_mode_action.setText(self._lookup_mode_label())
        if self.lookup_mode == "dictionary_app":
            self.statusBar().showMessage("Lookup mode: opens macOS Dictionary.app with dict://word")
        else:
            self.statusBar().showMessage("Lookup mode: in-app popup with sentence + root/stem helper")

    def open_word_in_dictionary_app(self, word: str) -> None:
        word = clean_lookup_word(word)
        if not word:
            return
        os.system(f"open 'dict://{quote(word)}' >/dev/null 2>&1 &")

    def current_chapter_title(self) -> str:
        if 0 <= self.current_chapter_index < len(self.book.chapters):
            return self.book.chapters[self.current_chapter_index].title
        return ""

    def lookup_word(self, clicked_word: str, sentence: str = "") -> None:
        clicked_word = clean_lookup_word(clicked_word)
        sentence = clean_lookup_word(sentence)
        if not clicked_word:
            return

        if self.lookup_mode == "dictionary_app":
            self.open_word_in_dictionary_app(clicked_word)
            return

        term_used, definition = dictionary_lookup(clicked_word)
        analysis = likely_arabic_analysis(clicked_word)
        record = LookupRecord(
            clicked_word=clicked_word,
            term_used=term_used,
            definition=definition,
            sentence=sentence,
            analysis=analysis,
            book=self.book.path.name if self.book.path else "",
            chapter=self.current_chapter_title(),
        )
        self.lookup_popup.show_lookup(record)

    def save_vocabulary_record(self, record_obj: object) -> None:
        if not isinstance(record_obj, LookupRecord):
            return
        record = record_obj
        analysis = record.analysis or likely_arabic_analysis(record.clicked_word)
        VOCAB_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        file_exists = VOCAB_CSV_PATH.exists()

        with VOCAB_CSV_PATH.open("a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "saved_at",
                    "word",
                    "dictionary_term",
                    "root_hint",
                    "stem_hint",
                    "normalized",
                    "pattern_hint",
                    "sentence",
                    "definition",
                    "book",
                    "chapter",
                    "notes",
                ],
            )
            if not file_exists:
                writer.writeheader()
            writer.writerow(
                {
                    "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "word": record.clicked_word,
                    "dictionary_term": record.term_used,
                    "root_hint": analysis.likely_root,
                    "stem_hint": analysis.stem,
                    "normalized": analysis.normalized,
                    "pattern_hint": analysis.pattern,
                    "sentence": record.sentence,
                    "definition": " ".join(record.definition.split()),
                    "book": record.book,
                    "chapter": record.chapter,
                    "notes": analysis.notes,
                }
            )

        self.statusBar().showMessage(f"Saved word to {VOCAB_CSV_PATH}")
        QMessageBox.information(self, "Saved word", f"Saved to:\n{VOCAB_CSV_PATH}")

    def open_vocab_csv(self) -> None:
        VOCAB_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not VOCAB_CSV_PATH.exists():
            with VOCAB_CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "saved_at",
                    "word",
                    "dictionary_term",
                    "root_hint",
                    "stem_hint",
                    "normalized",
                    "pattern_hint",
                    "sentence",
                    "definition",
                    "book",
                    "chapter",
                    "notes",
                ])
        os.system(f"open '{VOCAB_CSV_PATH}' >/dev/null 2>&1 &")

    def _sync_chapter_from_path(self, local_path: str) -> None:
        path = Path(local_path)
        for idx, chapter in enumerate(self.book.chapters):
            if chapter.file_path == path:
                self.current_chapter_index = idx
                self.chapter_list.blockSignals(True)
                self.chapter_list.setCurrentRow(idx)
                self.chapter_list.blockSignals(False)
                self.statusBar().showMessage(f"Chapter {idx + 1} of {len(self.book.chapters)}")
                return


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName(APP_ORG)
    app.setApplicationName(APP_NAME)

    window = MainWindow()
    window.show()

    if DCSCopyTextDefinition is None:
        QMessageBox.warning(
            window,
            "Dictionary Services unavailable",
            "The reader will open, but word lookup needs macOS PyObjC DictionaryServices.\n\n"
            "Install it with:\n"
            "pip install pyobjc-framework-DictionaryServices",
        )

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
