"""
server.py
==========

A small Flask API for translating SubRip subtitle (.srt) files from one
language into another.  The service reuses the translation logic from
`translate_srt.py` and can operate in two modes:

* **Offline mode** (default): uses Argos Translate to perform the
  translation locally.  This requires the `argostranslate` Python package and
  the appropriate `.argosmodel` file to be installed on the server.

* **API mode**: forwards translation requests to a LibreTranslate‑compatible
  HTTP API.  You can point this at a public instance or your own
  self‑hosted service.

Use this service to provide translation functionality to other machines on
your network (e.g. Sonarr/Radarr or external scripts).

The `/translate-srt` endpoint accepts a multipart form upload with the
subtitle file and optional parameters.  It returns the translated subtitle
file as plain text with a suggested filename.
"""

import argparse
import io
from flask import Flask, request, Response

# Import translation helpers from the CLI script
# These functions are defined in translate_srt.py in the same directory.
from translate_srt import (
    parse_srt,
    translate_line_preserve_tags,
    get_offline_translator,
    translate_via_api,
)

app = Flask(__name__)


def translate_srt_content(
    content: str,
    source_lang: str,
    target_lang: str,
    mode: str = "offline",
    api_url: str = "https://translate.argosopentech.com/translate",
) -> str:
    """Translate the contents of an SRT file.

    Args:
        content: The raw contents of the .srt file as a string.
        source_lang: ISO 639‑1 code of the source language (e.g. ``"en"``).
        target_lang: ISO 639‑1 code of the target language (e.g. ``"nb"``).
        mode: ``"offline"`` to use Argos Translate or ``"api"`` to use
            a LibreTranslate‑compatible HTTP service.
        api_url: URL of the translation API when in API mode.

    Returns:
        A string containing the translated subtitle file.
    """
    entries = parse_srt(content)

    # Determine translation function based on mode
    if mode == "offline":
        translator_fn = get_offline_translator(source_lang, target_lang)
        # Fallback to API if offline translator isn't available
        if translator_fn is None:
            translator_fn = lambda txt: translate_via_api(txt, source_lang, target_lang, api_url)
    else:
        translator_fn = lambda txt: translate_via_api(txt, source_lang, target_lang, api_url)

    output_lines = []
    for entry in entries:
        # First two lines are index and timing
        output_lines.append(entry[0])
        if len(entry) > 1:
            output_lines.append(entry[1])
        # Translate any dialogue lines (from the third line onwards)
        for line in entry[2:]:
            output_lines.append(translate_line_preserve_tags(line, translator_fn))
        # Separate entries with a blank line
        output_lines.append("")

    return "\n".join(output_lines)


@app.route("/translate-srt", methods=["POST"])
def translate_srt_endpoint() -> Response:
    """Handle file uploads and return the translated subtitle file."""
    uploaded_file = request.files.get("file")
    if not uploaded_file:
        return Response("No file provided", status=400)

    source_lang = request.form.get("source_lang", "en")
    target_lang = request.form.get("target_lang", "nb")
    mode = request.form.get("mode", "offline")
    api_url = request.form.get(
        "api_url",
        "https://translate.argosopentech.com/translate",
    )

    # Read the uploaded file into memory (decode using UTF-8 with fallback)
    raw_data = uploaded_file.read()
    try:
        content = raw_data.decode("utf-8")
    except UnicodeDecodeError:
        # Try Latin-1 if UTF-8 fails
        content = raw_data.decode("latin-1")

    # Translate the subtitle content
    translated_content = translate_srt_content(
        content, source_lang, target_lang, mode=mode, api_url=api_url
    )

    # Construct filename: original basename + target language code
    original_name = uploaded_file.filename or "subtitle.srt"
    base = original_name.rsplit(".", 1)[0]
    translated_filename = f"{base}.{target_lang}.srt"

    # Return as plain text with a Content-Disposition header
    return Response(
        translated_content,
        mimetype="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={translated_filename}",
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the subtitle translation API server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to listen on")
    parser.add_argument("--port", default=8000, type=int, help="Port to listen on")
    parser.add_argument(
        "--debug", action="store_true", help="Enable Flask debug mode"
    )
    args = parser.parse_args()

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
