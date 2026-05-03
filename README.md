# Web Summarizer

## Project overview

**Web Summarizer** is an integrated toolkit for **extracting**, **transcribing**, and **intelligently summarizing** content across **web pages**, **podcast-style audio**, **long-form video** (lectures / slide-heavy material), and **meeting materials** (recordings plus timestamped screenshots). Processing runs locally; it combines browser automation (Microsoft Edge), **iFlytek** long-form speech recognition, and **Volcengine Doubao** (OpenAI-compatible) text and multimodal APIs.

A **FastAPI** application (`web_service.py`) exposes the same capabilities through a browser UI and a small HTTP task API, so you can run jobs from the desktop or from another device on your LAN.

---

## Core capabilities

### 1. Web summarization

#### Supported platforms and behavior

**Zhihu**

- **Question pages**: extract the question title, description, and answer bodies where the site structure allows.
- **Column / article pages**: extract title, author metadata, main text, and images.
- **Comments**: recursive / threaded comment extraction is implemented where the page module supports it.

**Xiaohongshu (RED)**

- **Notes**: title, author, body text, and images.
- **Images**: multimodal understanding and summarization paths (Doubao vision) when wired through the Xiaohongshu summary pipeline.
- **Comments**: main comments and nested replies, preserving hierarchy where available.

**WeChat official articles** (`mp.weixin.qq.com`)

- Extract article title, author, body, and embedded images.

**Generic web pages**

- Fallback extraction for sites without a dedicated parser: identify and pull the primary readable content.

#### Technical approach

**Anti-detection and session handling**

- **User-Agent rotation** and realistic header sets (`useragents.py`).
- **Full HTTP-style headers** where appropriate (Accept, Referer, etc.).
- **Persistent browser profiles** per platform so cookies and login state survive across runs when you need logged-in content.
- **Overlay / login handling**: platform-specific logic to deal with dialogs that block content when not logged in.

**Content extraction**

- **Scrolling / lazy load**: automated scrolling so deferred content loads before capture.
- **Element targeting**: combined strategies (classes, ids, XPath, etc.) per platform module.
- **Sanity checks**: basic validation to avoid saving empty or obviously wrong bodies.
- **Image deduplication**: by URL and, where implemented, by content fingerprinting.

**Storage and downstream processing**

- **Safe filenames**: preserve CJK characters, strip unsafe symbols (`util/_save_raw_text.py`).
- **Folder layout**: outputs organized by platform, title, and timestamps as implemented in each flow.
- **Tags**: generated from content (`util/generate_tags.py`) and used to organize outputs (`util/organize_by_tags.py`).
- **Markdown**: unified save path via `util/save_to_markdown.py`; Xiaohongshu may use **`util/summary_xhs.py`** for multimodal-aware summaries.
- **Chunking**: long pages are split (`util/chunk_content.py`) before LLM calls; **`util/generate_summary.py`** summarizes chunks and can merge them into one document.
- **Edge WebDriver**: version alignment helper in **`util/edge_driver_manager.py`**.

#### Key files (web)

| File | Purpose |
|------|---------|
| `main.py` | CLI entry for a single URL (runs dependency checks, then `process_url`). |
| `base.py` | Shared summarizer / browser utilities. |
| `zhihu.py` | Zhihu-specific fetch and DOM logic. |
| `xiaohongshu.py` | Xiaohongshu-specific fetch and DOM logic. |
| `weixin.py` | WeChat article fetch and extraction. |
| `elsepage.py` | Generic-page summarizer. |
| `util/process_url.py` | Orchestrates fetch → summary → save; returns the **final** markdown path (including renames such as `domain_hash_summary.md`). |
| `util/chunk_content.py` | Splits long text for batched LLM calls. |
| `util/generate_summary.py` | Web text summarization (chunked + merge). |
| `util/generate_tags.py` | Tag generation for organization and discovery. |
| `util/organize_by_tags.py` | Moves or links outputs under tag-oriented structure. |
| `util/save_to_markdown.py` | Writes markdown and metadata from LLM output. |
| `util/summary_xhs.py` | Xiaohongshu-oriented multimodal summarization. |
| `util/_save_raw_text.py` | Raw text / filename helpers. |
| `dependency_check.py` | Verifies Python imports before long runs. |

---

### 2. Audio processing

#### Supported platforms

**Xiaoyuzhou (Cosmos)**

- Resolve show/episode metadata and direct audio URL (`xiaoyuzhoufm.py`).

**Ximalaya**

- Same class of metadata + audio URL resolution (`ximalaya.py`).

**NetEase Cloud Music (podcast pages)**

- Episode metadata + audio URL (`wangyiyun.py`).

#### Technical approach

**Speech recognition (iFlytek)**

- **Long-form file API** against `raasr.xfyun.cn` (upload + poll for result).
- **Hot words**: optional keywords from title/description to bias ASR (`util/hot_words.py`).
- **Speaker / role hints**: role-related parameters are passed where the API and pipeline support them.

**Audio preprocessing**

- **Format conversion** with **pydub**; **FFmpeg** is expected on `PATH`.
- **Sample rate**: normalized toward **16 kHz** mono WAV as required by the ASR pipeline.
- **Channels**: stereo down-mixed to mono when needed.

**Transcript summarization**

- Transcripts are **split into chunks** under a character budget (`chunk_content`) so each LLM request stays manageable.
- **`generate_audio_summary`** in `util/generate_summary.py` corrects obvious ASR errors and produces structured markdown summaries; long episodes imply **multiple sequential LLM calls** (plan runtime accordingly). Server-side runs can report **progress callbacks** into the web UI.

#### Key files (audio)

| File | Purpose |
|------|---------|
| `audio_main.py` | Interactive CLI: paste episode URL; writes a timestamped folder (e.g. under Desktop). |
| `xiaoyuzhoufm.py` | Xiaoyuzhou parser. |
| `ximalaya.py` | Ximalaya parser. |
| `wangyiyun.py` | NetEase parser. |
| `util/audio_utils.py` | Download, WAV prep, iFlytek client, JSON normalization, helpers used by ASR and video audio tracks. |
| `util/web_pipelines.py` | `run_audio_url_to_dir` — full audio pipeline for the web service into `service_runtime/outputs/<task_id>/`. |

#### Typical outputs (CLI audio folder)

Naming is prefix-based (platform + sanitized title + timestamps may appear in filenames):

- Original download, `*_16k.wav`, raw ASR JSON, plain transcript text, and `*_summary.md`.

---

### 3. Video analysis

#### Feature areas

**Slide / “PPT” detection**

- Detect slide-like full-frame changes using computer-vision pipelines (`util/video_utils.py`).
- Tunable sampling rate (`sample_rate`: frames processed per second of video in the main CLI path).
- Stability heuristics to avoid saving duplicate near-identical frames.
- Timestamps recorded per exported slide image.

**Audio track**

- Extract audio from the container, then run the same family of **iFlytek** transcription utilities as other modules (`util/audio_utils.py`).

**Audio–video alignment**

- Align slide timeline with transcript segments (`util/audio_video_sync.py`).
- Associate spoken content with the slide visible at that time.

**Intelligent summary**

- **Multimodal fusion**: combine slide images, transcript text, and metadata (`util/video_summary.py`).
- **Structured output**: sectioned reports suitable for study notes.
- **Timeline-oriented summaries**: content ordered along the media timeline when the generator is configured that way.

**Usage tracking**

- Optional **token / cost style reports** via `util/llm_usage_tracker.py` when enabled in the video flow.

#### Technical notes

- **OpenCV**-based frame differencing and background modeling (e.g. MOG2-style change detection) for robust slide transition discovery.
- **Pillow / NumPy** for image handling and numerical work alongside OpenCV.

#### Key files (video)

| File | Purpose |
|------|---------|
| `video_main.py` | CLI: `python video_main.py <video_path> [--sample-rate N]`. |
| `util/video_utils.py` | Frame sampling, change detection, slide export. |
| `util/audio_video_sync.py` | Synchronization between slides and speech. |
| `util/video_summary.py` | Builds multimodal / structured summaries from aligned data. |

#### Typical output layout

Default: a sibling directory `<video_stem>_分析结果/` next to the source file, containing slide images, transcript JSON, sync metadata, `video_summary.md`, processing logs/reports, and optional LLM usage reports.

---

### 4. Meeting processing

#### Feature areas

**Audio transcription**

- Common meeting formats ingested, converted when needed, and sent through **iFlytek** long ASR.
- Retry-friendly design around network and quota behavior.

**Screenshot linkage**

- **Timestamp parsing** from filenames: multiple patterns (e.g. `HHMMSS`, `HH:MM:SS`, `MM:SS`, plain seconds).
- **Nearest-time matching** between transcript segments and images.

**Multimodal minutes**

- Combine transcript + images using **Doubao multimodal** (`util/multimodal_summary.py`) when “understand screenshots” is enabled; otherwise transcript-first or link-only behavior.

**SRT subtitles**

- Standard **SRT** from transcript.
- Variant with **embedded image references** aligned to time.

#### Technical notes

- Regex-heavy filename analysis for timestamps.
- Image resize / format normalization before vision API calls where applicable.
- Context from speech helps interpret what a slide or screen capture is about.

#### Key files (meeting)

| File | Purpose |
|------|---------|
| `meeting_main.py` | CLI on a folder path; interactive choice for multimodal vs link-only images. |
| `util/multimodal_summary.py` | Multimodal summarization and text fallback. |
| `util/web_pipelines.py` | `run_meeting_zip_to_dir` — unpack ZIP and run meeting pipeline for the web app. |

#### Typical outputs

- Transcription JSON, `.srt`, image-augmented SRT, and `meeting_summary_<timestamp>.md`.

---

## Web application (FastAPI)

From the `web_summarizer` directory:

```bash
uvicorn web_service:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000/`. Credentials are **not** entered in the browser: they are read from **`config.json`** on the server.

**Task model**: one background worker thread — jobs are serialized.

| Method | Path | Role |
|--------|------|------|
| `GET` | `/` | Hosted UI (`ui/index.html`). |
| `GET` | `/api/health` | Liveness. |
| `GET` | `/api/service-urls` | LAN-friendly base URLs. |
| `POST` | `/api/tasks/web/url` | `{"url": "..."}`. |
| `POST` | `/api/tasks/audio/url` | `{"url": "..."}`. |
| `POST` | `/api/tasks/video/upload` | Multipart video + optional `sample_rate`. |
| `POST` | `/api/tasks/meeting/upload` | Multipart `.zip` + `understand_images`. |
| `GET` | `/api/tasks/{id}` | `status`, `progress`, `message`, `download_url` when finished. |
| `GET` | `/api/tasks/{id}/download` | Final **Markdown** file. |

Web task outputs live under **`service_runtime/outputs/<task_id>/`** (and uploads under `service_runtime/uploads/`).

---

## Architecture: AI services

### Doubao (Volcengine Ark)

- **OpenAI-compatible** HTTP API (`base_url`, `api_key`, `model`).
- **Text** summarization for web and chunked audio transcripts.
- **Multimodal** paths for Xiaohongshu, meetings, and video summaries as connected in code.
- Tunable **`temperature`**, **`max_tokens`**, **`timeout`**, retries.

### iFlytek (long-form file recognition)

- **REST** workflow on **`raasr.xfyun.cn`** (upload + poll).
- Requires **`appid`** and **`secret`**.
- Benefits from **stable DNS** and outbound HTTPS to China-region endpoints.

### Core technology stack (representative)

| Layer | Technologies |
|--------|----------------|
| Browser automation | Selenium 4.x, Edge WebDriver, `selenium-wire` where interception is needed |
| Vision / video | OpenCV, Pillow, NumPy |
| Audio | pydub, FFmpeg |
| HTML / text | BeautifulSoup, trafilatura, lxml (as pulled in by dependencies) |
| HTTP | `requests`, `urllib3` |
| LLM client | `openai` Python SDK |
| Web API | FastAPI, Uvicorn, Pydantic, `python-multipart` |

---

## Repository layout

```text
web_summarizer/
├── main.py
├── web_service.py
├── base.py
├── zhihu.py
├── xiaohongshu.py
├── weixin.py
├── elsepage.py
├── useragents.py
├── audio_main.py
├── audio_base.py
├── video_main.py
├── meeting_main.py
├── xiaoyuzhoufm.py
├── ximalaya.py
├── wangyiyun.py
├── dependency_check.py
├── config.json
├── ui/
│   └── index.html
├── service_runtime/          # runtime uploads + outputs (exclude from VCS if desired)
└── util/
    ├── config_manager.py
    ├── process_url.py
    ├── edge_driver_manager.py
    ├── chunk_content.py
    ├── generate_summary.py
    ├── generate_tags.py
    ├── organize_by_tags.py
    ├── save_to_markdown.py
    ├── summary_xhs.py
    ├── multimodal_summary.py
    ├── audio_utils.py
    ├── hot_words.py
    ├── web_pipelines.py
    ├── video_utils.py
    ├── audio_video_sync.py
    ├── video_summary.py
    ├── llm_usage_tracker.py
    ├── _save_raw_text.py
    └── …
```

---

## Usage examples

### Web (CLI)

```bash
cd web_summarizer
python dependency_check.py
python main.py "https://www.zhihu.com/question/…"
python main.py "https://www.xiaohongshu.com/…" --output note.md
python main.py "https://mp.weixin.qq.com/…"
python main.py "https://example.com/article"
```

### Audio (CLI)

```bash
python audio_main.py
# Paste Xiaoyuzhou / Ximalaya / NetEase podcast URL when prompted.
```

### Video (CLI)

```bash
python video_main.py lecture.mp4
python video_main.py lecture.mp4 --sample-rate 5
```

### Meeting (CLI)

```bash
python meeting_main.py "C:\path\to\folder_with_audio_and_screenshots"
```

Follow the interactive prompt to enable or disable multimodal image understanding.

---

## Configuration (`config.json`)

Central configuration is read through **`util/config_manager.py`**. Keep real keys **out of public repositories**.

```json
{
  "doubao": {
    "api_key": "your_doubao_api_key",
    "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    "model": "your_model_id",
    "timeout": 120,
    "max_tokens": 20000,
    "temperature": 0.2
  },
  "xunfei": {
    "appid": "your_xunfei_appid",
    "secret": "your_xunfei_secret",
    "base_url": "https://api.xfyun.cn",
    "timeout": 60
  },
  "system": {
    "max_retries": 3,
    "chunk_size": 2000,
    "default_encoding": "utf-8",
    "log_level": "INFO"
  },
  "audio": {
    "sample_rate": 16000,
    "channels": 1,
    "bit_depth": 16,
    "format": "wav"
  }
}
```

**Programmatic access:**

```python
from util.config_manager import get_doubao_config, get_xunfei_config
```

---

## Dependencies

- **Python**: 3.10+ recommended (3.12 works with the current code).
- Run **`python dependency_check.py`** — it prints a consolidated `pip install …` line for whatever is missing.
- **FFmpeg** must be available for typical audio/video conversion paths.
- **Microsoft Edge** must be installed for Selenium-based web capture.

Representative package families (exact versions evolve with your environment):

| Area | Packages |
|------|-----------|
| Automation | `selenium`, `selenium-wire`, WebDriver tooling |
| Vision | `opencv-python`, `numpy`, `Pillow` |
| Audio | `pydub` |
| Parsing | `beautifulsoup4`, `trafilatura`, `lxml` |
| HTTP | `requests` |
| LLM | `openai` |
| Web app | `fastapi`, `uvicorn`, `pydantic`, `python-multipart` |

---

## Operational notes

- **DNS**: failures resolving `raasr.xfyun.cn` are environment/DNS issues, not URL typos in code.
- **Long audio summaries**: many chunks ⇒ many LLM round-trips; the process may sit on “chunk *i*” for up to your configured **timeout** per call.
- **Downloads (web tasks)**: summaries may be saved under a hashed filename; the web layer tracks the **final** path returned from `process_url`.

You can add companion documents (e.g. deeper meeting or video guides) next to this README whenever your team needs them; this file is the **single umbrella** description of the project as shipped in this tree.
