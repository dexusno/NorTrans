"""
translate_srt.py
=================

This script translates the text in a SubRip subtitle (.srt) file from one
language into another while preserving the original subtitle layout and
timing information.  It offers two translation back‑ends:

* **API mode** (default): uses a LibreTranslate‑compatible HTTP API to
  translate each line of dialogue.  This mode requires network access
  to a translation service such as the public ``translate.argosopentech.com``
  instance or a self‑hosted LibreTranslate server.  API mode only depends
  on Python’s standard library (``urllib`` and ``json``) and therefore runs
  on a fresh Python installation without additional packages.

* **Offline mode**: uses the ``argostranslate`` Python library and a
  pre‑installed Argos Translate model to perform translations locally.  This
  mode requires the user to install the ``argostranslate`` package and
  the appropriate ``.argosmodel`` file for the source/target language pair.
  Offline mode will be selected automatically when ``--mode offline`` is
  supplied.

Regardless of mode, the script preserves subtitle ordering, time codes and
markup tags (for example ``<i>`` for italics).  Only plain text outside of
angle bracket tags is translated.  Lines containing numbers or timing
information are left untouched.

Usage examples::

    # Translate an English subtitle to Norwegian using a public API
    python translate_srt.py --input movie.en.srt --output movie.nb.srt \
        --api-url https://translate.argosopentech.com/translate \
        --source-lang en --target-lang nb

    # Translate using an offline Argos Translate model (requires package/model)
    python translate_srt.py --input movie.en.srt --output movie.nb.srt \
        --mode offline --source-lang en --target-lang nb

Command line arguments:

``--input``         Path to the input .srt file.
``--output``        Path where the translated subtitle file will be saved.
``--source-lang``   ISO 639‑1 language code of the source subtitles (default: en).
``--target-lang``   ISO 639‑1 language code of the output subtitles (default: nb).
``--api-url``       URL of a LibreTranslate‑compatible translation endpoint
                    (default: ``https://translate.argosopentech.com/translate``).
``--mode``          Translation mode: ``api`` (default) or ``offline``.

The script will detect and report errors such as missing input files or
unsupported configuration.  If using offline mode without the required
dependencies, it falls back to API mode and warns the user.

Author: NorTrans project
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from typing import Callable, List

try:
    # ``requests`` is optional; use standard library if not available.
    import requests  # type: ignore
    HAVE_REQUESTS = True
except ImportError:
    HAVE_REQUESTS = False


def translate_via_api(text: str, source: str, target: str, api_url: str) -> str:
    """Translate a string using a LibreTranslate compatible HTTP API.

    Args:
        text: The input text to translate.
        source: ISO 639‑1 code of the source language.
        target: ISO 639‑1 code of the target language.
        api_url: Base URL of the translation endpoint (e.g. ``/translate``).

    Returns:
        The translated text returned by the API.  If the API returns an
        unexpected response format, the original text is returned.
    """
    # Short‑circuit empty strings to avoid unnecessary network calls.
    if not text.strip():
        return text

    # Prepare the data payload.  LibreTranslate accepts application/x-www-form-urlencoded
    # or JSON bodies.  For maximum compatibility we send urlencoded form data.
    params = {
        "q": text,
        "source": source,
        "target": target,
        "format": "text",
    }
    data = urllib.parse.urlencode(params).encode("utf-8")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        request = urllib.request.Request(api_url, data=data, headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response:
            resp_data = response.read().decode("utf-8")
    except Exception as exc:
        sys.stderr.write(f"[Warning] API translation failed: {exc}\n")
        return text

    try:
        json_resp = json.loads(resp_data)
    except json.JSONDecodeError:
        # Unexpected response; return original text
        sys.stderr.write(f"[Warning] API returned non‑JSON response: {resp_data!r}\n")
        return text

    # LibreTranslate returns {"translatedText": "..."}.  Other services may use
    # different keys.  Try several possibilities before falling back to original.
    for key in ("translatedText", "translation", "translated_text", "translated"):
        if isinstance(json_resp, dict) and key in json_resp:
            return str(json_resp[key])
    # If response is just a string, return it.
    if isinstance(json_resp, str):
        return json_resp
    return text


def get_offline_translator(source: str, target: str):
    """Attempt to create an offline translator using Argos Translate.

    Returns a callable that takes a string and returns its translation.  If
    Argos Translate is not installed or the model for the requested language
    pair is missing, returns ``None``.
    """
    try:
        import argostranslate.package
        import argostranslate.translate
    except ImportError:
        return None

    # Ensure languages are installed.  The user must have installed the
    # appropriate .argosmodel file beforehand using ``argospm``.
    installed_langs = argostranslate.translate.get_installed_languages()
    from_lang = next((lang for lang in installed_langs if lang.code == source), None)
    to_lang = next((lang for lang in installed_langs if lang.code == target), None)
    if not from_lang or not to_lang:
        return None
    translator = from_lang.get_translation(to_lang)
    return translator.translate


def parse_srt(content: str) -> List[List[str]]:
    """Parse the contents of an SRT file into a list of entries.

    Each entry is a list of lines including the index, time span and one or
    more text lines.  Blank lines between entries are not preserved.
    """
    # Normalize line endings
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    entries_raw = content.strip().split("\n\n")
    entries: List[List[str]] = []
    for raw in entries_raw:
        lines = raw.split("\n")
        if lines:
            entries.append(lines)
    return entries


TAG_REGEX = re.compile(r"(<[^>]+>)")


def translate_line_preserve_tags(line: str, translate_fn: Callable[[str], str]) -> str:
    """Translate a single line while preserving HTML/markup tags.

    Args:
        line: The input subtitle line, possibly containing tags like <i>.
        translate_fn: A function that translates plain text.

    Returns:
        The translated line with tags left in place.
    """
    parts = TAG_REGEX.split(line)
    translated_parts: List[str] = []
    for part in parts:
        # If the part matches the tag regex, leave it unchanged
        if TAG_REGEX.fullmatch(part):
            translated_parts.append(part)
        else:
            # Otherwise translate the plain text; preserve whitespace
            if part.strip():
                translated = translate_fn(part)
            else:
                translated = part
            translated_parts.append(translated)
    return "".join(translated_parts)


def translate_srt_entries(entries: List[List[str]], translate_fn: Callable[[str], str]) -> List[List[str]]:
    """Translate the text lines of SRT entries using the provided function.

    Args:
        entries: A list of SRT entries, where each entry is a list of lines.
        translate_fn: A function that takes a string and returns its translation.

    Returns:
        A new list of entries with translated text lines.  Index and time lines
        are left unchanged.
    """
    translated_entries: List[List[str]] = []
    for entry in entries:
        if len(entry) < 3:
            # Not a standard entry; copy unchanged
            translated_entries.append(entry.copy())
            continue
        index_line = entry[0]
        time_line = entry[1]
        text_lines = entry[2:]
        new_text_lines: List[str] = []
        for text in text_lines:
            # Translate each line individually while preserving tags
            new_text_lines.append(translate_line_preserve_tags(text, translate_fn))
        translated_entries.append([index_line, time_line] + new_text_lines)
    return translated_entries


def srt_entries_to_string(entries: List[List[str]]) -> str:
    """Convert a list of SRT entries back into the text form of an SRT file."""
    return "\n\n".join("\n".join(entry) for entry in entries) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate subtitles in an SRT file.")
    parser.add_argument("--input", required=True, help="Path to the input .srt file")
    parser.add_argument("--output", required=True, help="Path to write the translated .srt file")
    parser.add_argument("--source-lang", default="en", help="Source language code (default: en)")
    parser.add_argument("--target-lang", default="nb", help="Target language code (default: nb for Norwegian Bokmål)")
    parser.add_argument("--api-url", default="https://translate.argosopentech.com/translate",
                        help="URL of the LibreTranslate compatible API endpoint")
    parser.add_argument("--mode", choices=["api", "offline"], default="api",
                        help="Translation mode: api (default) or offline")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        sys.stderr.write(f"Error: input file '{args.input}' does not exist\n")
        sys.exit(1)

    # Decide which translation function to use
    translate_fn: Callable[[str], str]
    if args.mode == "offline":
        offline_translator = get_offline_translator(args.source_lang, args.target_lang)
        if offline_translator is None:
            sys.stderr.write("[Warning] Offline mode requested but Argos Translate is not configured. "
                             "Falling back to API mode.\n")
        else:
            translate_fn = lambda text: offline_translator(text)
        if offline_translator is None:
            translate_fn = lambda text: translate_via_api(text, args.source_lang, args.target_lang, args.api_url)
    else:
        translate_fn = lambda text: translate_via_api(text, args.source_lang, args.target_lang, args.api_url)

    # Read and parse the input file
    with open(args.input, "r", encoding="utf-8-sig") as f:
        content = f.read()
    entries = parse_srt(content)

    # Translate entries
    translated_entries = translate_srt_entries(entries, translate_fn)

    # Write output file
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(srt_entries_to_string(translated_entries))
    print(f"Translation complete. Output written to {args.output}")


if __name__ == "__main__":
    main()
