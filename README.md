# NorTrans – English→Norwegian subtitle translation

NorTrans is a simple project for translating `.srt` subtitle files from **English** into **Norwegian Bokmål** (language code `nb`).  It combines open‑source tools such as **Argos Translate**, **LibreTranslate** and **Lingarr** to automate subtitle translation in your media workflow.

This document explains how to set up the infrastructure, run the provided translation scripts and integrate translation into Sonarr/Radarr via Lingarr.

## Overview

### Why translate subtitles?
Many media releases include only English subtitles.  If you prefer to watch films and series with Norwegian subtitles, it is desirable to automatically translate existing `.srt` files while keeping their timing and layout.

### Key components

| Component | Purpose |
| --- | --- |
| **Argos Translate** | Offline translation library and model format for Python.  It supports installing language packages such as English→Norwegian and can be called from scripts. |
| **LibreTranslate** | Web API built on Argos Translate.  You can self‑host it to expose `/translate` endpoints for Lingarr and CLI scripts. |
| **Argos Translate Files** | Helper library that translates whole files (including `.srt`) using Argos Translate. |
| **Lingarr** | Subtitle translation orchestrator.  It watches your Sonarr/Radarr libraries and automatically translates subtitles using a configured service. |

## 1. Setting up Lingarr with LibreTranslate
If you want a fully automated solution that integrates directly with Sonarr and Radarr, deploy Lingarr alongside a LibreTranslate server.  Lingarr will monitor your media folders, download English subtitles via Sonarr/Radarr and translate them into Norwegian.

### 1.1 Prerequisites

- A server with Docker and Docker Compose (your HP dual Xeon server works well).
- API keys for your Sonarr and Radarr instances (see each application’s settings).
- Disk space and network access to download language models.

### 1.2 Language configuration
Lingarr uses environment variables to select the translation service and define the source and target languages.  Use a minified JSON array with `name` and `code` keys.  For English→Norwegian:

```json
[{"name":"English","code":"en"},{"name":"Norwegian Bokmål","code":"nb"}]
```

### 1.3 Docker Compose example
Below is a minimal `docker‑compose.yml` that runs Lingarr together with a LibreTranslate container on the same network.  Replace `/path/to/media` with your actual media directories and set the Sonarr/Radarr URLs and API keys.

```yaml
version: "3.8"

services:
  lingarr:
    image: lingarr/lingarr:latest
    container_name: lingarr
    restart: unless-stopped
    environment:
      ASPNETCORE_URLS: "http://+:9876"
      MAX_CONCURRENT_JOBS: "1"
      RADARR_URL: "http://radarr:7878"
      RADARR_API_KEY: "<your-radarr-api-key>"
      SONARR_URL: "http://sonarr:8989"
      SONARR_API_KEY: "<your-sonarr-api-key>"
      SERVICE_TYPE: "libretranslate"
      SOURCE_LANGUAGES: '[{"name":"English","code":"en"}]'
      TARGET_LANGUAGES: '[{"name":"Norwegian Bokmål","code":"nb"}]'
      LIBRE_TRANSLATE_URL: "http://libretranslate:5000"
    volumes:
      - /path/to/media/movies:/movies
      - /path/to/media/tv:/tv
      - /path/to/lingarr/config:/app/config
    networks:
      - lingarr
    depends_on:
      - libretranslate

  libretranslate:
    image: libretranslate/libretranslate:latest
    container_name: libretranslate
    restart: unless-stopped
    environment:
      LT_LOAD_ONLY: "en,nb"     # download only English and Norwegian models
      LT_DISABLE_WEB_UI: "true"  # disable web UI
    ports:
      - "5000:5000"
    volumes:
      - /path/to/libretranslate/data:/home/libretranslate/.local/share/argos-translate
    networks:
      - lingarr

networks:
  lingarr:
    external: false
```

Start the stack with `docker compose up -d`.  Lingarr will then monitor the configured `/movies` and `/tv` directories.  When Sonarr or Radarr downloads a new item with English subtitles, Lingarr will translate each file into Norwegian using LibreTranslate.

## 2. Using the command‑line script
For manual translation, use the `translate_srt.py` script included in this repository.  It reads an input `.srt` file, translates the dialogue and writes a new `.srt` while preserving indices, timing and formatting tags.

### 2.1 Prerequisites

- Python 3 on Windows or Linux.
- **API mode:** network access to a LibreTranslate endpoint (e.g. the public `https://translate.argosopentech.com/translate` or your self‑hosted instance).
- **Offline mode:** install the `argostranslate` package and the English→Norwegian model (`translate-en_nb-1_9.argosmodel`).  Use `argospm` to install the model.

### 2.2 Installation
Clone this repository or copy `translate_srt.py` to your PC.  Install any necessary packages:

```bash
# Install Argos Translate only if you plan to use offline mode
pip install argostranslate
# Download and install the model (adjust the filename if newer versions exist)
argospm install translate-en_nb-1_9.argosmodel
```

### 2.3 Usage examples

```bash
# Translate using a LibreTranslate API (replace URL if using your own server)
python translate_srt.py \
    --input Subs/episode.srt --output Subs/episode.nb.srt \
    --api-url http://localhost:5000/translate --source-lang en --target-lang nb

# Translate locally using Argos Translate (requires model)
python translate_srt.py --input movie.srt --output movie.nb.srt --mode offline
```

The script will detect missing files or unsupported configuration and report errors.  In offline mode, it falls back to API mode if dependencies are missing.

## 3. Running your own translation API
The `server.py` file in this repository exposes a simple Flask service that accepts an uploaded `.srt` file and returns the translated result.  It uses the same translation logic as the CLI script and can operate in API or offline mode.

### 3.1 Deployment

Install Python 3 and Flask on your server:

```bash
pip install flask argostranslate  # argostranslate only needed for offline mode
argospm install translate-en_nb-1_9.argosmodel  # optional for offline mode
```

Copy `server.py` and `translate_srt.py` to your server and start the API:

```bash
python server.py --host 0.0.0.0 --port 8000
```

### 3.2 Using the API
Send a POST request with your subtitle file.  For example using `curl`:

```bash
curl -F "file=@episode.srt" -F "source_lang=en" -F "target_lang=nb" \
     http://server-ip:8000/translate-srt --output episode.nb.srt
```

You can adjust the language codes, choose `mode=offline` to force offline translation and set `api_url` to point to any LibreTranslate‑compatible service.

## 4. Costs and recommendations
A self‑hosted solution (Lingarr + LibreTranslate) is completely free and satisfies the budget constraint.  Argos Translate and Lingarr are open source.  Paid services such as DeepL or OpenAI can offer higher quality and are supported by Lingarr via different `SERVICE_TYPE` values.

Your HP server with a GTX 1070 and ample RAM is more than sufficient to run LibreTranslate and Argos Translate.  CPU translation works; GPU acceleration can improve throughput if supported by the models.

## 5. Conclusion
NorTrans demonstrates how to combine open‑source tools to translate subtitles from English to Norwegian automatically.  For full automation, deploy Lingarr and LibreTranslate using the Docker example.  For occasional manual translation, use `translate_srt.py` locally or run `server.py` to expose a simple translation API.

Everything can be hosted on your own infrastructure without monthly fees, and you can always switch to a paid translation provider later by changing Lingarr’s settings.
