"""
Clip Clean
==========

A local-only desktop utility for cleaning raw Ctrl+A / Ctrl+C copies from
websites, PDFs, and documents.

It removes common navigation, legal boilerplate, timestamps, page numbers, and
stray UI lines while preserving paragraphs, lists, tables, and code blocks. The
cleaning is done entirely with Python string operations and regular expressions.
No API keys, network calls, AI services, or telemetry are used.

Installation
------------
    py -m pip install customtkinter pyperclip

Run
---
    py clip_clean.py

Shortcut
--------
    Ctrl + Enter   Clean the pasted text

pyperclip is optional at runtime: if it is unavailable, the app falls back to
Tk's built-in clipboard.
"""

from __future__ import annotations

import re
import time
import unicodedata

try:
    import customtkinter as ctk
except ImportError:
    raise SystemExit(
        "CustomTkinter is not installed.\n"
        "Install the requirements with:  py -m pip install customtkinter pyperclip"
    ) from None

try:
    import pyperclip
except ImportError:
    pyperclip = None


# ---------------------------------------------------------------------------
# Parsing constants
# ---------------------------------------------------------------------------

FENCE_RE = re.compile(r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
CODE_TOKEN_PREFIX = "\ue000CODEBLOCK_"
CODE_TOKEN_RE = re.compile(r"^\ue000CODEBLOCK_(\d+)\ue000$")

LIST_ITEM_RE = re.compile(
    r"^[ \t]*(?P<marker>(?:[-*+•‣◦▪▫–—]|\d{1,3}[.)]|[A-Za-z][.)]|"
    r"\(\d{1,3}\)|\([A-Za-z]\)))[ \t]+(?P<content>\S.*)$"
)

TERMINAL_RE = re.compile(r"[.!?;:…](?:[\"'”’)\]]*)\s*$")
URL_ONLY_RE = re.compile(r"^(?:https?://|www\.)\S+$", re.I)
HTML_TAG_ONLY_RE = re.compile(r"^</?[A-Za-z][^>]*>$")
PAGE_NUMBER_RE = re.compile(
    r"^\s*(?:page|p\.)\s*\d+(?:\s*(?:of|/)\s*\d+)?\s*$", re.I
)
COUNT_ONLY_RE = re.compile(
    r"^\s*\d[\d,.]*\s*(?:views?|comments?|likes?|shares?|votes?|"
    r"upvotes?|followers?|subscribers?)\s*$",
    re.I,
)
TIMESTAMP_RE = re.compile(
    r"""(?ix)^\s*(?:
        just\s+now
      | today
      | yesterday
      | \d+\s*(?:seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?)\s+ago
      | \d+\s*(?:min|mins|minutes?)\s+read
      | (?:posted|published|updated|modified)\s+(?:on\s+)?[^|]{0,60}
      | \d{1,2}:\d{2}(?::\d{2})?\s*(?:[ap]\.?m\.?)?(?:\s*[A-Z]{2,4})?
      | \d{1,2}[/-]\d{1,2}[/-]\d{2,4}
      | \d{4}-\d{2}-\d{2}
      | (?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?
        \s+\d{1,2},?\s+\d{4}
    )\s*$"""
)

COPYRIGHT_LINE_RE = re.compile(r"(?i)^\s*(?:copyright\b|©|\(c\)\s*\d{4})")
BOILERPLATE_RE = re.compile(
    r"""(?ix)
    (?:
        all\s+rights\s+reserved
      | privacy\s+(?:policy|notice|settings)
      | terms\s+(?:of\s+(?:service|use)|and\s+conditions)
      | cookie\s+(?:policy|settings|preferences|consent|notice|banner)
      | accept\s+(?:all\s+)?cookies?
      | (?:we|this\s+(?:site|website))\s+uses?\s+cookies?
      | subscribe\s+(?:to|for)\b.*\bnewsletter
      | newsletter\s+subscription
      | sign\s*(?:in|up)\s*(?:/|\|)\s*(?:register|sign\s*up)
      | (?:sign|log)\s+in
      | skip\s+to\s+(?:main\s+)?content
      | back\s+to\s+top
      | (?:advertisement|advertising|sponsored|promoted)
      | follow\s+us
      | share\s+(?:this|on)
      | read\s+more
      | learn\s+more
      | load\s+more
      | show\s+more
      | view\s+all
      | leave\s+a\s+(?:comment|reply)
      | post\s+a\s+comment
      | related\s+(?:articles?|posts?|stories?|content)
      | recommended\s+(?:for\s+you|articles?|posts?)
      | you\s+may\s+also\s+like
      | more\s+from\b
      | download\s+(?:our|the)\s+app
      | (?:enable|turn\s+on)\s+javascript
      | do\s+not\s+sell\s+my\s+personal\s+information
      | manage\s+(?:preferences|cookies?)
      | powered\s+by
    )
    """
)

# Generic navigation/UI labels. These are removed when they make up an entire
# short line, even if the line is title-cased.
NAV_TERMS = {
    "home", "homepage", "home page", "menu", "main menu", "navigation",
    "toggle navigation", "search", "about", "about us", "contact", "contact us",
    "share", "share this", "reply", "login", "log in", "sign in", "sign up",
    "register", "subscribe", "newsletter", "next", "previous", "back",
    "read more", "learn more", "view all", "see all", "comments", "comment",
    "related posts", "related articles", "follow us", "sitemap", "rss", "faq",
    "help", "support", "careers", "jobs", "advertise", "press", "blog", "news",
    "events", "products", "services", "solutions", "pricing", "features",
    "customers", "partners", "resources", "docs", "documentation", "community",
    "developers", "status", "settings", "account", "profile", "logout",
    "log out", "close", "open", "get started", "contact sales", "book a demo",
    "request a demo", "try it free", "free trial", "privacy", "privacy policy",
    "terms", "terms of service", "cookies", "cookie policy", "accept cookies",
    "skip to content", "back to top",
}

SMALL_TITLE_WORDS = {
    "a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into",
    "of", "on", "or", "over", "per", "the", "to", "up", "via", "vs", "with",
}


class RefinementError(ValueError):
    """Raised when there is nothing cleanable in the supplied text."""


# ---------------------------------------------------------------------------
# Small classification helpers
# ---------------------------------------------------------------------------


def _normalise_raw_text(raw: str) -> str:
    """Normalize line endings, invisible characters, and Unicode forms."""

    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = (
        text.replace("\u00a0", " ")
        .replace("\u202f", " ")
        .replace("\u200b", "")
        .replace("\u200c", "")
        .replace("\u200d", "")
        .replace("\ufeff", "")
    )
    return unicodedata.normalize("NFKC", text)


def _indent_width(line: str) -> int:
    """Return the visual indentation width, expanding tabs to four spaces."""

    expanded = line.expandtabs(4)
    return len(expanded) - len(expanded.lstrip(" "))


def _is_placeholder(line: str) -> bool:
    return bool(CODE_TOKEN_RE.fullmatch(line.strip()))


def _code_token(index: int) -> str:
    return f"{CODE_TOKEN_PREFIX}{index}\ue000"


def _is_markdown_heading(line: str) -> bool:
    return bool(re.match(r"^\s*#{1,6}\s+\S", line))


def _is_list_line(line: str) -> bool:
    return bool(LIST_ITEM_RE.match(line))


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.count("|") >= 2


def _is_blockquote(line: str) -> bool:
    return bool(re.match(r"^\s*>\s?", line))


def _ends_terminal(line: str) -> bool:
    return bool(TERMINAL_RE.search(line.rstrip()))


def _starts_lowercase(line: str) -> bool:
    for character in line.lstrip("\"'“‘([<*-•> "):
        if character.isalpha():
            return character.islower()
    return False


def _word_count(line: str) -> int:
    return len(line.split())


def _match_key(line: str) -> str:
    """Normalize a line for comparison against the navigation vocabulary."""

    key = re.sub(r"\s+", " ", line.strip().casefold())
    return key.strip(" .:;!?…—–-|•·/›»")


def _is_title_caseish(line: str) -> bool:
    """Return True when a line looks like a title rather than a sentence."""

    words = [word.strip(".,:;!?()[]{}\"'“”‘’") for word in line.split()]
    words = [word for word in words if word]
    if not words:
        return False

    for index, word in enumerate(words):
        first_alpha = next((ch for ch in word if ch.isalpha()), "")
        if not first_alpha:
            continue
        if index > 0 and word.casefold() in SMALL_TITLE_WORDS:
            continue
        if not first_alpha.isupper():
            return False
    return True


def _looks_like_code_line(line: str) -> bool:
    """Conservatively identify code so its internal spacing is preserved."""

    stripped = line.lstrip(" \t")
    if not stripped:
        return False

    if stripped in {"{", "}", "};", "});", "]", ")", "});", "```"}:
        return True

    if stripped.startswith(
        ("//", "/*", "*/", "#include", "#define", "<?", "<!", "</", "<!--")
    ):
        return True

    if re.match(r"(?i)^(?:def|class)\s+[A-Za-z_]\w*.*:\s*$", stripped):
        return True

    if re.match(
        r"(?i)^(?:function|const|let|var|public|private|protected|static|"
        r"void|int|float|double|char|bool|string|struct|enum|interface|type|"
        r"import|from|package|namespace|using)\b",
        stripped,
    ) and (
        stripped.endswith(("{", ";", ":", ")"))
        or any(ch in stripped for ch in "(){}[]=;")
    ):
        return True

    if re.match(
        r"(?i)^(?:for|while|if|elif|else|switch|case|try|catch|except|"
        r"finally|with|return|yield|throw|new)\b",
        stripped,
    ) and any(ch in stripped for ch in "(){}[]=;"):
        return True

    if re.match(
        r"(?i)^(?:select|insert|update|delete|create|alter|drop)\b", stripped
    ) and any(
        f" {keyword} " in f" {stripped.upper()} "
        for keyword in ("FROM", "WHERE", "VALUES", "INTO", "TABLE", "SET")
    ):
        return True

    if "=>" in stripped or "</" in stripped or "/>" in stripped:
        return True

    if stripped.endswith((";", "{", "}")) and any(
        ch in stripped for ch in "=(){}[]"
    ):
        return True

    if re.match(r"^[A-Za-z_]\w*\s*\([^)]*\)\s*[;{]?$", stripped) and any(
        ch in stripped for ch in "=;"
    ):
        return True

    if sum(stripped.count(ch) for ch in "{}[]") >= 2 and "=" in stripped:
        return True

    return False


def _is_indented_continuation(line: str) -> bool:
    return (
        bool(line.strip())
        and _indent_width(line) >= 4
        and not _is_list_line(line)
        and not _is_placeholder(line)
    )


def _extract_code_blocks(text: str) -> tuple[str, list[str]]:
    """
    Replace fenced and indented code blocks with placeholders.

    Protecting code early means the later boilerplate, short-line, and
    paragraph-stitching passes cannot alter code layout.
    """

    blocks: list[str] = []
    lines = text.split("\n")

    # First protect Markdown-style fenced blocks.
    fenced: list[str] = []
    index = 0
    while index < len(lines):
        match = FENCE_RE.match(lines[index])
        if not match:
            fenced.append(lines[index])
            index += 1
            continue

        marker = match.group("fence")
        fence_char = marker[0]
        fence_length = len(marker)
        block = [lines[index]]
        index += 1

        closing_re = re.compile(
            rf"^[ \t]{{0,3}}{re.escape(fence_char)}{{{fence_length},}}[ \t]*$"
        )
        while index < len(lines):
            block.append(lines[index])
            if closing_re.match(lines[index]):
                index += 1
                break
            index += 1

        token = _code_token(len(blocks))
        blocks.append("\n".join(block))
        fenced.append(token)

    # Then protect indented code blocks that contain clear code signals.
    output: list[str] = []
    index = 0
    while index < len(fenced):
        line = fenced[index]

        if (
            not line.strip()
            or _is_placeholder(line)
            or _indent_width(line) < 4
            or _is_list_line(line)
            or not _looks_like_code_line(line)
        ):
            output.append(line)
            index += 1
            continue

        block: list[str] = [line]
        end = index + 1
        while end < len(fenced):
            candidate = fenced[end]

            if not candidate.strip():
                lookahead = end
                while lookahead < len(fenced) and not fenced[lookahead].strip():
                    lookahead += 1
                if (
                    lookahead < len(fenced)
                    and _is_indented_continuation(fenced[lookahead])
                ):
                    block.extend(fenced[end:lookahead])
                    end = lookahead
                    continue
                break

            if _is_indented_continuation(candidate):
                block.append(candidate)
                end += 1
                continue

            break

        token = _code_token(len(blocks))
        blocks.append("\n".join(block).rstrip())
        output.append(token)
        index = end

    return "\n".join(output), blocks


def _normalise_line(line: str) -> str:
    """Normalize one non-code line while preserving list/table structure."""

    if not line.strip():
        return ""
    if _is_placeholder(line):
        return line.strip()

    line = line.replace("\t", "    ")

    if _is_markdown_heading(line):
        return re.sub(r"[ \t]+", " ", line.strip())

    if _looks_like_code_line(line):
        return line.rstrip()

    if _is_table_row(line):
        return re.sub(r"[ \t]+", " ", line.strip())

    if _is_blockquote(line):
        content = re.sub(r"[ \t]+", " ", line.strip()[1:].strip())
        return f"> {content}" if content else ""

    list_match = LIST_ITEM_RE.match(line)
    if list_match:
        content = re.sub(
            r"[ \t]+", " ", line[list_match.start("content"):]
        ).strip()
        if not content:
            return ""
        indent = _indent_width(line)
        prefix = "  " * min(indent // 2, 4) if indent >= 2 else ""
        return f"{prefix}{list_match.group('marker')} {content}"

    return re.sub(r"[ \t]+", " ", line.strip())


def _is_junk_line(line: str) -> bool:
    """Detect page numbers, counters, timestamps, URLs, and symbol-only lines."""

    if (
        not line.strip()
        or _is_placeholder(line)
        or _looks_like_code_line(line)
        or _is_markdown_heading(line)
        or _is_list_line(line)
        or _is_table_row(line)
        or _is_blockquote(line)
    ):
        return False

    stripped = line.strip()

    if not any(character.isalpha() for character in stripped):
        return True
    if URL_ONLY_RE.match(stripped) or HTML_TAG_ONLY_RE.match(stripped):
        return True
    if PAGE_NUMBER_RE.match(stripped) or COUNT_ONLY_RE.match(stripped):
        return True
    if TIMESTAMP_RE.match(stripped):
        return True

    return False


def _is_boilerplate_line(line: str) -> bool:
    """Detect legal, cookie, newsletter, and footer boilerplate."""

    if _is_placeholder(line) or _looks_like_code_line(line):
        return False

    stripped = line.strip()

    if COPYRIGHT_LINE_RE.match(stripped):
        return True
    if re.search(r"©\s*(?:19|20)\d{2}", stripped):
        return True

    # Keep the check line-oriented and short-line biased so a long article
    # paragraph that merely mentions a policy is not discarded.
    if _word_count(stripped) <= 24 and BOILERPLATE_RE.search(stripped):
        return True

    return False


def _is_nav_line(line: str) -> bool:
    """Detect short navigation labels and breadcrumb-style menu lines."""

    if (
        not line.strip()
        or _is_placeholder(line)
        or _looks_like_code_line(line)
        or _is_markdown_heading(line)
        or _is_table_row(line)
        or _is_blockquote(line)
    ):
        return False

    key = _match_key(line)
    if key in NAV_TERMS:
        return True

    if re.search(r"[|•·›»]|\s+/\s+|\s+>\s+", line):
        parts = [
            part
            for part in re.split(r"\s*(?:[|•·›»]|/|>)\s*", line)
            if part.strip()
        ]
        if len(parts) >= 2:
            keys = [_match_key(part) for part in parts]
            if all(part_key in NAV_TERMS for part_key in keys):
                return True

            # Breadcrumb chains such as "Home > Blog > Article" are discarded
            # when they start with a known navigation label and stay short.
            if (
                keys[0] in NAV_TERMS
                and not _ends_terminal(line)
                and all(_word_count(part) <= 5 for part in parts)
            ):
                return True

    return False


def _looks_like_heading_text(line: str) -> bool:
    """Lightweight heading detector used to keep wrapped prose separate."""

    stripped = line.strip()
    if not stripped:
        return False
    if _is_markdown_heading(stripped):
        return True
    if _is_list_line(stripped) or _is_table_row(stripped) or _is_blockquote(stripped):
        return False
    if _ends_terminal(stripped):
        return False

    words = stripped.split()
    if len(words) > 10:
        return False

    letters = [ch for ch in stripped if ch.isalpha()]
    if letters and all(ch.isupper() for ch in letters):
        return True
    if _is_title_caseish(stripped):
        return True
    if re.match(
        r"(?i)^(?:chapter|section|part|appendix|step)\s+\d+\b", stripped
    ):
        return True

    return False


def _can_stitch(previous: str, current: str) -> bool:
    """Return True when two lines are wrapped parts of one paragraph."""

    if not previous or not current:
        return False
    if _ends_terminal(previous) or _looks_like_heading_text(previous):
        return False
    if not _starts_lowercase(current):
        return False

    for line in (previous, current):
        if (
            _is_placeholder(line)
            or _looks_like_code_line(line)
            or _is_markdown_heading(line)
            or _is_list_line(line)
            or _is_table_row(line)
            or _is_blockquote(line)
        ):
            return False

    return True


def _stitch_paragraphs(lines: list[str]) -> list[str]:
    """Join lines that wrap mid-sentence, including PDF hyphenation breaks."""

    stitched: list[str] = []
    for line in lines:
        if not line.strip():
            if stitched and stitched[-1] != "":
                stitched.append("")
            continue

        if stitched and stitched[-1] and _can_stitch(stitched[-1], line):
            previous = stitched[-1]
            if previous.endswith("-") and _starts_lowercase(line):
                stitched[-1] = previous[:-1] + line
            else:
                stitched[-1] = f"{previous} {line}"
        else:
            stitched.append(line)

    return stitched


def _is_heading_candidate(line: str, isolated: bool) -> bool:
    stripped = line.strip()
    if _is_markdown_heading(stripped):
        return True
    if re.match(
        r"(?i)^(?:chapter|section|part|appendix|step)\s+\d+\b", stripped
    ):
        return True
    if not isolated:
        return False

    words = stripped.split()
    if len(words) > 10:
        return False

    letters = [ch for ch in stripped if ch.isalpha()]
    if letters and all(ch.isupper() for ch in letters):
        return True
    if _is_title_caseish(stripped):
        return True

    # Sentence-case headings such as "Project notes" are common in documents.
    # Isolation by blank lines is enough context to preserve them.
    first_alpha = next((ch for ch in stripped if ch.isalpha()), "")
    return bool(first_alpha and first_alpha.isupper())


def _drop_orphan_lines(lines: list[str]) -> list[str]:
    """Remove short, punctuation-free navigation remnants."""

    result: list[str] = []
    for index, line in enumerate(lines):
        if not line.strip():
            if result and result[-1] != "":
                result.append("")
            continue

        if (
            _is_placeholder(line)
            or _looks_like_code_line(line)
            or _is_markdown_heading(line)
            or _is_list_line(line)
            or _is_table_row(line)
            or _is_blockquote(line)
            or _ends_terminal(line)
        ):
            result.append(line)
            continue

        stripped = line.strip()
        if _word_count(stripped) >= 4 or len(stripped) >= 32:
            result.append(line)
            continue

        previous_blank = index == 0 or not lines[index - 1].strip()
        next_blank = index == len(lines) - 1 or not lines[index + 1].strip()
        isolated = previous_blank and next_blank

        if _is_heading_candidate(stripped, isolated):
            result.append(line)
        # Otherwise this is an orphan nav label such as "Share" or "Reply".

    return result


def _collapse_blank_lines(text: str) -> str:
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n(?:[ \t]*\n){2,}", "\n\n", text)
    return text.strip()


def clean_text_content(raw: str) -> str:
    """
    Clean raw copied content and return the useful text.

    Edge cases:
      * Empty input raises RefinementError.
      * Input containing only boilerplate raises RefinementError.
      * Fenced and indented code is protected from scrubbing.
      * Lists and tables are retained.
    """

    if not raw or not raw.strip():
        raise RefinementError("There is nothing to clean.")

    text = _normalise_raw_text(raw)
    text, code_blocks = _extract_code_blocks(text)

    lines = [_normalise_line(line) for line in text.split("\n")]

    filtered: list[str] = []
    for line in lines:
        if not line.strip():
            filtered.append("")
            continue
        if _is_junk_line(line):
            continue
        if _is_boilerplate_line(line):
            continue
        if _is_nav_line(line):
            continue
        filtered.append(line)

    filtered = _stitch_paragraphs(filtered)
    filtered = _drop_orphan_lines(filtered)

    cleaned = _collapse_blank_lines("\n".join(filtered))

    # Restore code only after all line-level heuristics have finished.
    for index, block in enumerate(code_blocks):
        cleaned = cleaned.replace(_code_token(index), block)
    cleaned = cleaned.strip()

    if not cleaned:
        raise RefinementError("No readable content remained after removing page clutter.")

    return cleaned


# ===========================================================================
# USER INTERFACE
# ===========================================================================

BG = "#080C12"
CARD = "#101720"
EDITOR_BG = "#0B1119"
BORDER = "#223044"
BORDER_SOFT = "#1A2635"
TEXT = "#E8EFF8"
TEXT_MUTED = "#8291A6"
TEXT_DIM = "#5E6D82"
ACCENT = "#4F8CFF"
ACCENT_HOVER = "#3B74E8"
ACCENT_DARK = "#142C4F"
GREEN = "#34D399"
AMBER = "#FBBF24"
RED = "#F87171"


class UniversalRefinerApp(ctk.CTk):
    """Main CustomTkinter window."""

    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")

        self.title("Clip Clean")
        self.geometry("1280x820")
        self.minsize(960, 660)
        self.configure(fg_color=BG)

        self.font_brand = ctk.CTkFont(family="Segoe UI", size=21, weight="bold")
        self.font_subtitle = ctk.CTkFont(family="Segoe UI", size=12)
        self.font_panel_title = ctk.CTkFont(
            family="Segoe UI", size=12, weight="bold"
        )
        self.font_small = ctk.CTkFont(family="Segoe UI", size=11)
        self.font_button = ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        self.font_body = ctk.CTkFont(family="Segoe UI", size=14)
        self.font_mono = ctk.CTkFont(family="Cascadia Code", size=13)

        self._status_after_id: str | None = None
        self._count_after_id: str | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_workspace()
        self._build_footer()

        self.bind("<Control-Return>", self._on_clean_shortcut)

        self.after(120, self.raw_text.focus_set)
        self._set_status("Ready. No data leaves this device.", "muted")

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 12))
        header.grid_columnconfigure(1, weight=1)

        logo = ctk.CTkFrame(
            header,
            width=44,
            height=44,
            corner_radius=12,
            fg_color=ACCENT_DARK,
            border_width=1,
            border_color="#214A80",
        )
        logo.grid(row=0, column=0, rowspan=2, padx=(0, 13), sticky="w")
        logo.grid_propagate(False)

        ctk.CTkLabel(
            logo,
            text="Aa",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=ACCENT,
        ).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            header,
            text="Clip Clean",
            font=self.font_brand,
            text_color=TEXT,
            anchor="w",
        ).grid(row=0, column=1, sticky="sw")

        ctk.CTkLabel(
            header,
            text="Pull the useful text out of any messy copy.",
            font=self.font_subtitle,
            text_color=TEXT_MUTED,
            anchor="w",
        ).grid(row=1, column=1, sticky="nw", pady=(1, 0))

        badge = ctk.CTkFrame(
            header,
            fg_color="#0D1A17",
            corner_radius=20,
            border_width=1,
            border_color="#1D3A32",
        )
        badge.grid(row=0, column=2, rowspan=2, sticky="e")

        ctk.CTkLabel(
            badge,
            text="●",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=GREEN,
        ).pack(side="left", padx=(13, 6), pady=7)

        ctk.CTkLabel(
            badge,
            text="100% LOCAL",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#8EE8C8",
        ).pack(side="left", padx=(0, 13), pady=7)

    def _build_workspace(self) -> None:
        workspace = ctk.CTkFrame(self, fg_color="transparent")
        workspace.grid(row=1, column=0, sticky="nsew", padx=28, pady=(4, 0))
        workspace.grid_columnconfigure(0, weight=1, uniform="editor")
        workspace.grid_columnconfigure(1, minsize=150)
        workspace.grid_columnconfigure(2, weight=1, uniform="editor")
        workspace.grid_rowconfigure(0, weight=1)

        raw_card, self.raw_count = self._make_card(
            workspace,
            number="01",
            title="RAW WEB/DOCUMENT PASTE",
            hint="Paste any page, PDF, or document with Ctrl+A, then Ctrl+C.",
        )
        raw_card.grid(row=0, column=0, sticky="nsew")

        self.raw_text = self._make_textbox(raw_card, self.font_mono)
        self.raw_text.grid(
            row=2, column=0, sticky="nsew", padx=14, pady=(0, 14)
        )
        self.raw_text.bind("<KeyRelease>", self._schedule_count_update)
        self.raw_text.bind("<ButtonRelease-1>", self._schedule_count_update)

        rail = ctk.CTkFrame(workspace, fg_color="transparent")
        rail.grid(row=0, column=1, sticky="nsew")

        rail_inner = ctk.CTkFrame(rail, fg_color="transparent")
        rail_inner.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            rail_inner,
            text="→",
            font=ctk.CTkFont(family="Segoe UI", size=28),
            text_color="#36516F",
        ).pack(pady=(0, 4))

        self.clean_button = ctk.CTkButton(
            rail_inner,
            text="Clean Text",
            width=132,
            height=42,
            corner_radius=11,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="#FFFFFF",
            font=self.font_button,
            command=self.clean_text,
        )
        self.clean_button.pack()

        ctk.CTkLabel(
            rail_inner,
            text="Ctrl + Enter",
            font=self.font_small,
            text_color=TEXT_DIM,
        ).pack(pady=(7, 0))

        refined_card, self.refined_count = self._make_card(
            workspace,
            number="02",
            title="REFINED CONTENT",
            hint="Paragraphs, lists, and code are preserved where possible.",
        )
        refined_card.grid(row=0, column=2, sticky="nsew")

        self.refined_text = self._make_textbox(refined_card, self.font_body)
        self.refined_text.grid(
            row=2, column=0, sticky="nsew", padx=14, pady=(0, 14)
        )
        self.refined_text.bind("<KeyRelease>", self._schedule_count_update)
        self.refined_text.bind("<ButtonRelease-1>", self._schedule_count_update)

    def _make_card(
        self, parent: ctk.CTkFrame, number: str, title: str, hint: str
    ) -> tuple[ctk.CTkFrame, ctk.CTkLabel]:
        card = ctk.CTkFrame(
            parent,
            fg_color=CARD,
            corner_radius=16,
            border_width=1,
            border_color=BORDER,
        )
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(2, weight=1)

        heading = ctk.CTkFrame(card, fg_color="transparent")
        heading.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 0))
        heading.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            heading,
            text=number,
            width=28,
            height=22,
            corner_radius=7,
            fg_color="#172438",
            text_color=ACCENT,
            font=ctk.CTkFont(family="Cascadia Code", size=10, weight="bold"),
        ).grid(row=0, column=0, padx=(0, 9))

        ctk.CTkLabel(
            heading,
            text=title,
            font=self.font_panel_title,
            text_color=TEXT,
            anchor="w",
        ).grid(row=0, column=1, sticky="w")

        count_label = ctk.CTkLabel(
            heading,
            text="0 chars",
            font=self.font_small,
            text_color=TEXT_DIM,
            anchor="e",
        )
        count_label.grid(row=0, column=2, sticky="e")

        ctk.CTkLabel(
            card,
            text=hint,
            font=self.font_small,
            text_color=TEXT_DIM,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(5, 10))

        return card, count_label

    def _make_textbox(
        self, parent: ctk.CTkFrame, font: ctk.CTkFont
    ) -> ctk.CTkTextbox:
        return ctk.CTkTextbox(
            parent,
            fg_color=EDITOR_BG,
            border_width=1,
            border_color=BORDER_SOFT,
            border_spacing=8,
            corner_radius=11,
            text_color=TEXT,
            font=font,
            wrap="word",
            undo=True,
            scrollbar_button_color="#26384F",
            scrollbar_button_hover_color="#3A526F",
        )

    def _build_footer(self) -> None:
        bar = ctk.CTkFrame(
            self,
            fg_color=CARD,
            corner_radius=14,
            border_width=1,
            border_color=BORDER,
        )
        bar.grid(row=2, column=0, sticky="ew", padx=28, pady=(14, 22))
        bar.grid_columnconfigure(1, weight=1)

        self.status_dot = ctk.CTkLabel(
            bar,
            text="●",
            width=12,
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=TEXT_DIM,
        )
        self.status_dot.grid(row=0, column=0, padx=(17, 7), pady=12)

        self.status_label = ctk.CTkLabel(
            bar,
            text="Ready.",
            font=self.font_small,
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.status_label.grid(row=0, column=1, sticky="ew", pady=12)

        self.clear_button = ctk.CTkButton(
            bar,
            text="Clear All",
            width=96,
            height=32,
            corner_radius=9,
            fg_color="transparent",
            hover_color="#1A2635",
            border_width=1,
            border_color=BORDER,
            text_color=TEXT_MUTED,
            font=self.font_small,
            command=self.clear_all,
        )
        self.clear_button.grid(row=0, column=2, padx=(8, 8), pady=8)

        self.copy_button = ctk.CTkButton(
            bar,
            text="Copy to Clipboard",
            width=172,
            height=32,
            corner_radius=9,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="#FFFFFF",
            text_color_disabled="#6A7C93",
            font=self.font_small,
            command=self.copy_to_clipboard,
            state="disabled",
        )
        self.copy_button.grid(row=0, column=3, padx=(0, 8), pady=8)

    def _on_clean_shortcut(self, _event=None):
        self.clean_text()
        return "break"

    def clean_text(self) -> None:
        raw = self.raw_text.get("1.0", "end-1c")
        if not raw.strip():
            self._set_status("Paste some text first.", "warning")
            self.raw_text.focus_set()
            self.bell()
            return

        started = time.perf_counter()
        try:
            cleaned = clean_text_content(raw)
        except RefinementError as exc:
            self._set_status(str(exc), "error", reset_after=6500)
            self.raw_text.focus_set()
            self.bell()
            return
        except Exception:
            self._set_status(
                "Could not clean that text. Try copying it again.",
                "error",
                reset_after=6500,
            )
            self.bell()
            return

        elapsed_ms = max(1, round((time.perf_counter() - started) * 1000))

        self.refined_text.delete("1.0", "end")
        self.refined_text.insert("1.0", cleaned)
        self.refined_text.see("1.0")
        self.copy_button.configure(state="normal")
        self._update_counts()

        self._set_status(
            f"Cleaned in {elapsed_ms} ms · {len(cleaned):,} characters kept.",
            "success",
            reset_after=4500,
        )

    def copy_to_clipboard(self) -> None:
        text = self.refined_text.get("1.0", "end-1c").strip()
        if not text:
            self._set_status("There is no refined text to copy yet.", "warning")
            return

        try:
            if pyperclip is not None:
                pyperclip.copy(text)
            else:
                raise RuntimeError("pyperclip is not installed")
        except Exception:
            try:
                self.clipboard_clear()
                self.clipboard_append(text)
                self.update_idletasks()
            except Exception:
                self._set_status(
                    "Clipboard unavailable. Select the text and press Ctrl+C.",
                    "error",
                    reset_after=6000,
                )
                return

        self._set_status(
            "Copied! Refined text is on your clipboard.",
            "success",
            reset_after=2200,
        )

    def clear_all(self) -> None:
        had_content = bool(
            self.raw_text.get("1.0", "end-1c").strip()
            or self.refined_text.get("1.0", "end-1c").strip()
        )

        self.raw_text.delete("1.0", "end")
        self.refined_text.delete("1.0", "end")
        self.copy_button.configure(state="disabled")
        self._update_counts()
        self.raw_text.focus_set()

        if had_content:
            self._set_status("Cleared. Paste something new when ready.", "muted")
        else:
            self._set_status("Already empty. Paste something to begin.", "muted")

    def _set_status(
        self, message: str, tone: str = "muted", reset_after: int | None = None
    ) -> None:
        if self._status_after_id is not None:
            try:
                self.after_cancel(self._status_after_id)
            except Exception:
                pass
            self._status_after_id = None

        colors = {
            "muted": (TEXT_MUTED, TEXT_DIM),
            "success": ("#B7F7DF", GREEN),
            "warning": ("#FDE9A8", AMBER),
            "error": ("#FECACA", RED),
        }
        text_color, dot_color = colors.get(tone, colors["muted"])
        self.status_label.configure(text=message, text_color=text_color)
        self.status_dot.configure(text_color=dot_color)

        if reset_after is not None:
            self._status_after_id = self.after(
                reset_after,
                lambda: self._set_status(
                    "Ready. No data leaves this device.", "muted"
                ),
            )

    def _schedule_count_update(self, _event=None) -> None:
        if self._count_after_id is not None:
            try:
                self.after_cancel(self._count_after_id)
            except Exception:
                pass
        self._count_after_id = self.after(80, self._update_counts)

    def _update_counts(self) -> None:
        self._count_after_id = None
        raw_length = len(self.raw_text.get("1.0", "end-1c"))
        refined_length = len(self.refined_text.get("1.0", "end-1c"))
        self.raw_count.configure(
            text=f"{raw_length:,} char" if raw_length == 1 else f"{raw_length:,} chars"
        )
        self.refined_count.configure(
            text=(
                f"{refined_length:,} char"
                if refined_length == 1
                else f"{refined_length:,} chars"
            )
        )


def main() -> None:
    app = UniversalRefinerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
