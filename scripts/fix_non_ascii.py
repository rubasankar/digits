#!/usr/bin/env python3
"""
Normalize "typographic artifact" characters that AI code-generation tools
tend to sprinkle into source files (smart quotes, em/en dashes, non-breaking
spaces, zero-width characters, etc.) back to their plain-ASCII equivalents.

This is intentionally NOT a blanket unidecode pass. Blanket transliteration
would also mangle *deliberate* non-ASCII content that legitimately belongs
in a Django project -- currency symbols (₹, €, £), translated strings in
.po files, accented names in fixtures/tests, emoji in comments, etc.

Instead, we only touch a curated set of characters that are near-universally
AI-formatting mistakes rather than intentional content, and that are also
the ones most likely to actually break code (e.g. a curly quote where a
real string quote was meant, or a non-breaking space that silently causes
an IndentationError/SyntaxError).

Usage (e.g. as a pre-commit hook):
    fix_non_ascii.py file1.py file2.js ...
Exit code is non-zero if any files were modified, so pre-commit will ask
you to re-stage.
"""

import contextlib
import sys
from pathlib import Path
from typing import Any

from charset_normalizer import from_bytes

# File types that should be treated as text/source code.
TEXT_SUFFIXES = {
    ".py",
    ".pyi",
    ".html",
    ".htm",
    ".txt",
    ".md",
    ".rst",
    ".css",
    ".scss",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".env",
    ".sql",
    ".xml",
    ".csv",
}

# .po files intentionally contain msgid/msgstr with real, deliberate
# non-ASCII translated content -- never touch those.
EXCLUDED_SUFFIXES = {".po", ".mo"}

# Specific filenames to always skip, matched against the file's basename.
# Add anything here that should never be touched regardless of extension --
# e.g. this script itself (so a pre-commit run over "all files" can't
# rewrite its own source), lockfiles, migrations you don't want normalized, etc.
EXCLUDED_FILENAMES = {
    "fix_non_ascii.py",
}

# Curated map of "AI formatting artifact" characters -> ASCII replacement.
# Everything NOT in this map (currency symbols, accented letters, CJK,
# emoji, math symbols, etc.) is left completely untouched.
REPLACEMENTS: dict[str, str | int | None] = {
    # Smart / curly single quotes, primes
    "\u2018": "'",  # LEFT SINGLE QUOTATION MARK
    "\u2019": "'",  # RIGHT SINGLE QUOTATION MARK
    "\u201a": "'",  # SINGLE LOW-9 QUOTATION MARK
    "\u201b": "'",  # SINGLE HIGH-REVERSED-9 QUOTATION MARK
    "\u2032": "'",  # PRIME
    "\u00b4": "'",  # ACUTE ACCENT (often used as apostrophe)
    "\u0060": "`",  # GRAVE ACCENT, normalized form
    # Smart / curly double quotes
    "\u201c": '"',  # LEFT DOUBLE QUOTATION MARK
    "\u201d": '"',  # RIGHT DOUBLE QUOTATION MARK
    "\u201e": '"',  # DOUBLE LOW-9 QUOTATION MARK
    "\u201f": '"',  # DOUBLE HIGH-REVERSED-9 QUOTATION MARK
    "\u2033": '"',  # DOUBLE PRIME
    # Dashes / hyphens
    "\u2010": "-",  # HYPHEN
    "\u2011": "-",  # NON-BREAKING HYPHEN
    "\u2012": "-",  # FIGURE DASH
    "\u2013": "-",  # EN DASH
    "\u2014": "-",  # EM DASH
    "\u2015": "-",  # HORIZONTAL BAR
    "\u2212": "-",  # MINUS SIGN
    # Ellipsis
    "\u2026": "...",  # HORIZONTAL ELLIPSIS
    # Bullets (common in AI-generated comments/docstrings/lists)
    "\u2022": "*",  # BULLET
    "\u25cf": "*",  # BLACK CIRCLE
    "\u2023": "*",  # TRIANGULAR BULLET
    # Spaces that look like a normal space but aren't
    "\u00a0": " ",  # NO-BREAK SPACE
    "\u2000": " ",  # EN QUAD
    "\u2001": " ",  # EM QUAD
    "\u2002": " ",  # EN SPACE
    "\u2003": " ",  # EM SPACE
    "\u2004": " ",  # THREE-PER-EM SPACE
    "\u2005": " ",  # FOUR-PER-EM SPACE
    "\u2006": " ",  # SIX-PER-EM SPACE
    "\u2007": " ",  # FIGURE SPACE
    "\u2008": " ",  # PUNCTUATION SPACE
    "\u2009": " ",  # THIN SPACE
    "\u200a": " ",  # HAIR SPACE
    "\u202f": " ",  # NARROW NO-BREAK SPACE
    "\u205f": " ",  # MEDIUM MATHEMATICAL SPACE
    "\u3000": " ",  # IDEOGRAPHIC SPACE
    # Invisible / zero-width characters -- strip entirely
    "\u200b": "",  # ZERO WIDTH SPACE
    "\u200c": "",  # ZERO WIDTH NON-JOINER
    "\u200d": "",  # ZERO WIDTH JOINER
    "\u2060": "",  # WORD JOINER
    "\ufeff": "",  # BOM / ZERO WIDTH NO-BREAK SPACE
    "\u00ad": "",  # SOFT HYPHEN
}


def _decode(raw: bytes, result: Any) -> str | None:
    """Best-effort decode of `raw` using the detected charset match."""
    try:
        return str(result)
    except UnicodeDecodeError:
        pass

    try:
        return raw.decode(result.encoding or "utf-8")
    except UnicodeDecodeError, LookupError:
        return None


def normalize(text: str) -> str:
    """Replace only known AI-artifact characters; leave everything else."""
    return text.translate(str.maketrans(REPLACEMENTS))


def _is_eligible(path: Path) -> bool:
    """Should this path even be considered for normalization?"""
    suffix = path.suffix.lower()
    return (
        path.is_file()
        and suffix in TEXT_SUFFIXES
        and suffix not in EXCLUDED_SUFFIXES
        and path.name not in EXCLUDED_FILENAMES
    )


def _read_text(path: Path) -> str | None:
    """Read and decode a file's contents, or None if that isn't possible."""
    try:
        raw = path.read_bytes()
    except OSError:
        return None

    result = from_bytes(raw).best()
    if result is None:
        return None

    return _decode(raw, result)


def process(path: Path) -> bool:
    if not _is_eligible(path):
        return False

    original = _read_text(path)
    if original is None:
        return False

    converted = normalize(original)
    if converted == original:
        return False

    path.write_text(converted, encoding="utf-8", newline="")
    return True


def main() -> int:
    changed = False

    for filename in sys.argv[1:]:
        with contextlib.suppress(Exception):
            changed |= process(Path(filename))

    # Return non-zero if files were modified so pre-commit asks for re-stage.
    return 1 if changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
