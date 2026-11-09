# Clip Clean

A clean, local-only Windows desktop app for turning messy copied text from websites, PDFs, and documents into readable content.

![Clip Clean showing a messy web article on the left and the cleaned text on the right](docs/screenshots/01-cleaned-web-article.png)

## What it does

Paste anything with **Ctrl+A → Ctrl+C**, click **Clean Text**, and the app removes common page clutter while preserving the useful parts.

It removes:

- Copyright, privacy-policy, cookie, and newsletter boilerplate
- Navigation menus, breadcrumbs, and orphan labels such as "Home" or "Share"
- Page numbers, counters, timestamps, and symbol-only lines
- Wrapped-line breaks from PDFs and web copies
- Excessive whitespace and blank lines

It preserves:

- Paragraphs
- Bullet and numbered lists
- Tables
- Markdown headings
- Fenced and indented code blocks

All processing happens locally. There are no API calls, keys, accounts, or telemetry.

## See it in action

### Pull the useful text out of a messy web copy
![Clip Clean showing a raw web article beside its cleaned version](docs/screenshots/01-cleaned-web-article.png)
*Navigation links, timestamps, and footer text are removed while the article is kept.*

### Copy the result with confirmation
![Clip Clean showing the Copied! status after copying the refined text](docs/screenshots/02-copied-notification.png)
*The Copy to Clipboard action confirms success in the status bar.*

### Keep lists, tables, and code intact
![Clip Clean preserving a bullet list, numbered list, Markdown table, and Python code block](docs/screenshots/03-lists-tables-and-code.png)
*Structure embedded in the copy survives the cleanup pass.*

### Works in a smaller window
![Clip Clean resized to a compact 960x660 window with scrollable editors](docs/screenshots/04-compact-window.png)
*The two-panel layout stays usable when the window is resized.*

## How it works

Clip Clean processes text in a single pass through these stages:

1. **Normalize** — fix Unicode smart quotes, dashes, and stray control characters; collapse runs of spaces.
2. **Protect code** — fence and indented code blocks are tagged and held aside so the cleaning steps never touch them.
3. **Strip boilerplate** — copyright lines, cookie notices, newsletter prompts, privacy-policy fragments, and social-share labels are removed by pattern matching.
4. **Drop navigation noise** — breadcrumb trails, single-word orphan labels ("Home", "Menu", "Share"), page-number lines, timestamps, and symbol-only lines are discarded.
5. **Stitch paragraphs** — hard line-breaks inserted by PDF exporters and web scrapers are rejoined so each paragraph flows as one block.
6. **Collapse whitespace** — more than two consecutive blank lines are reduced to one.
7. **Restore code** — the protected blocks are placed back exactly where they were.

No AI model, API, or internet connection is involved at any step.

## Download and run

Download **clip_clean.exe** from the [Releases page](https://github.com/Icey067/Clipclean/releases/latest) and double-click it. No installation or Python required.

## Run from source

```powershell
py -m pip install -r requirements.txt
py clip_clean.py
```

Python 3.10 or newer is recommended.

## Build a standalone EXE

```powershell
py -m pip install pyinstaller
py -m PyInstaller --noconfirm --clean --noconsole --onefile --collect-all customtkinter clip_clean.py
```

The executable is created at:

```text
dist/clip_clean.exe
```

The `--collect-all customtkinter` flag is required because it packages CustomTkinter's theme and font assets alongside the binary.

`dist/` and `build/` are intentionally ignored by Git. Attach the generated EXE to a GitHub Release instead of committing it to the repository.

## Project structure

```text
.
├── clip_clean.py          # Application source and cleaning logic
├── requirements.txt       # Runtime dependencies
├── .gitignore
├── README.md
└── docs/
    └── screenshots/
        ├── 01-cleaned-web-article.png
        ├── 02-copied-notification.png
        ├── 03-lists-tables-and-code.png
        └── 04-compact-window.png
```

## Keyboard shortcut

- **Ctrl + Enter** — clean the pasted text

## Limitations

This is a heuristic cleaner, not an AI model. It is intentionally conservative, but unusual page layouts can still require a manual edit. Code is preserved reliably when it is fenced or clearly indented; heavily reformatted or image-based PDFs may not copy cleanly in the first place.

## Privacy

The application runs entirely on the local machine. It never uploads pasted text or uses an external service.
