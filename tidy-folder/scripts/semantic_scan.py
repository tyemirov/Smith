#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "mutagen>=1.47",
#   "openpyxl>=3.1",
#   "Pillow>=10.0",
#   "pypdf>=5.0",
# ]
# ///
"""Semantic inventory scanner for tidy-folder.

This helper gathers evidence from filenames, file contents, metadata, OCR
results, and media frame grabs so the tidy-folder workflow can classify files
by meaning instead of by extension.

Usage:
  ./semantic_scan.py /path/to/folder
  ./semantic_scan.py /path/to/folder --json
  ./semantic_scan.py /path/to/folder --manifest --autopilot
  ./semantic_scan.py /path/to/folder --manifest --autopilot --vision --vision-provider openai

The default output summarizes scores and uncertainty.
`--manifest --autopilot` emits a deterministic placement manifest intended
for fully automated execution. Files that score below confidence thresholds are
marked as low-confidence and routed through an internal refinement pass to reach
high-confidence destinations.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET

try:
    from pypdf import PdfReader  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    PdfReader = None

try:
    from PIL import Image
    from PIL.ExifTags import TAGS as PIL_EXIF_TAGS
except Exception:  # pragma: no cover - optional dependency
    Image = None
    PIL_EXIF_TAGS = {}

try:
    import mutagen  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    mutagen = None

try:
    from transformers import pipeline as hf_pipeline  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    hf_pipeline = None


TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'._+-]*")

DEFAULT_IGNORES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".venv",
    ".localized",
    "node_modules",
    "dist",
    "build",
    "coverage",
}

TEXT_EXTS = {
    ".txt",
    ".md",
    ".rst",
    ".log",
    ".xml",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".ics",
    ".llc",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".sh",
    ".bash",
}

CSV_EXTS = {".csv", ".tsv"}
JSON_EXTS = {".json"}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}
AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg"}
PDF_EXTS = {".pdf"}
DOCX_EXTS = {".docx"}
PPTX_EXTS = {".pptx"}
XLSX_EXTS = {".xlsx"}
OLD_OFFICE_EXTS = {".doc", ".xls", ".ppt"}

SOURCE_WEIGHTS = {
    "path": 3.0,
    "name": 3.0,
    "text": 2.0,
    "metadata": 2.2,
    "ocr": 3.0,
    "file": 1.0,
    "vision": 4.0,
}

PROJECT_STOP_TOKENS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "file",
    "files",
    "image",
    "images",
    "photo",
    "photos",
    "video",
    "videos",
    "audio",
    "document",
    "documents",
    "data",
    "stuff",
    "things",
    "items",
    "personal",
    "misc",
    "miscellaneous",
    "other",
    "general",
    "common",
    "shared",
    "resources",
    "assets",
    "materials",
    "archive",
    "old",
    "legacy",
    "downloads",
    "inbox",
    "new",
    "temp",
    "tmp",
    "untitled",
    "draft",
    "final",
    "copy",
    "test",
    "download",
    "screenshot",
    "screen",
    "recording",
    "recordings",
    "video",
    "audio",
    "img",
    "imgs",
    "img_",
    "jpg",
    "jpeg",
    "png",
    "heic",
    "webm",
    "mp4",
    "mov",
    "pdf",
    "docx",
    "xlsx",
    "csv",
    "json",
    "html",
    "htm",
}

TAXONOMY_HINT_MAX_DEPTH = 4
TAXONOMY_HINT_MIN_FILES = 2

TAXONOMY_HINT_PROJECT_CONTEXT_THRESHOLD = 3.4
WEAK_CONTEXT_SOURCE_SCALE = {
    "path": 0.45,
    "name": 0.45,
    "text": 1.2,
    "metadata": 1.2,
    "ocr": 1.2,
    "vision": 1.4,
    "file": 1.0,
}
VIDEO_FRAME_SAMPLE_OFFSETS = (0.25, 0.45, 0.65)
IMAGE_OCR_MAX_PIXELS = 20_000_000
IMAGE_OCR_TIMEOUT_SECONDS = 10
VIDEO_FRAME_OCR_TIMEOUT_SECONDS = 10
VISION_MODELS = (
    "Salesforce/blip-image-captioning-base",
    "Salesforce/blip-image-captioning-large",
)
OPENAI_VISION_MODEL = "gpt-4o-mini"
OPENAI_CHAT_COMPLETIONS_ENDPOINT = "https://api.openai.com/v1/chat/completions"
LOCAL_VISION_BOOTSTRAP_ENV = "TIDY_FOLDER_LOCAL_VISION_BOOTSTRAPPED"


WEAK_CONTEXT_REVIEW_TOP_MIN = 3.0
AUTOPILOT_REFINEMENT_PASSES = 3
AUTOPILOT_REFINEMENT_MIN_CONFIDENCE = 0.76
AUTOPILOT_REFINEMENT_MIN_SUPPORT = 2
AUTOPILOT_REFINEMENT_MIN_RATIO = 0.70
AUTOPILOT_REFINE_CONFIDENCE_GAP = 1.0
AUTOPILOT_REFINE_CONFIDENCE_THRESHOLD = 0.50

GENERIC_TAXONOMY_SEGMENTS = {
    "0",
    "2010s",
    "2020s",
    "3d",
    "about",
    "active",
    "archive",
    "backups",
    "backup",
    "bin",
    "code",
    "common",
    "commons",
    "data",
    "dev",
    "dev-tools",
    "downloads",
    "document",
    "documents",
    "docs",
    "dump",
    "files",
    "general",
    "home",
    "images",
    "inbox",
    "items",
    "learning",
    "legacy",
    "misc",
    "miscellaneous",
    "new",
    "notes",
    "old",
    "other",
    "pdf",
    "pdfs",
    "personal",
    "photos",
    "project",
    "projects",
    "public",
    "reference",
    "references",
    "refs",
    "resources",
    "samples",
    "scratch",
    "share",
    "shared",
    "sorted",
    "stuff",
    "temp",
    "temporary",
    "tmp",
    "to-sort",
    "to_sort",
    "tools",
    "work",
}

GENERIC_TAXONOMY_SEGMENTS = {segment.lower() for segment in GENERIC_TAXONOMY_SEGMENTS}

PRODUCTION_MODE_TAXONOMY_BLACKLIST = {
    "ai-generations",
}

PROJECT_INTERNAL_SEGMENTS = {
    "app",
    "apps",
    "bin",
    "build",
    "components",
    "config",
    "configs",
    "coverage",
    "dist",
    "examples",
    "fixtures",
    "lib",
    "logs",
    "node_modules",
    "scripts",
    "src",
    "styles",
    "test",
    "tests",
    "tmp",
    "tools",
    "utils",
}

MDLS_CONTENT_FIELDS = {
    "kMDItemAlbum",
    "kMDItemAlternateNames",
    "kMDItemAuthors",
    "kMDItemComment",
    "kMDItemComposer",
    "kMDItemDescription",
    "kMDItemDisplayName",
    "kMDItemFinderComment",
    "kMDItemHeadline",
    "kMDItemKeywords",
    "kMDItemMusicalGenre",
    "kMDItemTitle",
    "kMDItemWhereFroms",
}

PROJECT_MARKER_FILES = {
    ".git",
    ".gitignore",
    "cargo.toml",
    "cmakelists.txt",
    "makefile",
    "readme.md",
    "build.gradle",
    "go.mod",
    "package.json",
    "package-lock.json",
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "vite.config.js",
    "vite.config.ts",
}


@dataclass(frozen=True)
class Rule:
    home: str
    patterns: tuple[tuple[str, float], ...]
    kind_bonus: dict[str, float] = field(default_factory=dict)


RULES: tuple[Rule, ...] = (
    Rule(
        "Dev-Tools/Google-OAuth",
        (
            ("client_secret", 5.0),
            ("oauth", 4.0),
            ("token_uri", 5.0),
            ("auth_uri", 5.0),
            ("googleusercontent", 4.0),
            ("javascript_origins", 3.0),
        ),
    ),
    Rule(
        "Dev-Tools/Residential-Proxies",
        (
            ("webshare", 5.0),
            ("brightdata", 5.0),
            ("proxy", 3.0),
            ("residential proxies", 4.0),
        ),
    ),
    Rule(
        "Dev-Tools/Browser-Auth",
        (
            ("session required", 5.0),
            ("cookie", 2.5),
            ("cookies", 2.5),
            ("browser auth", 4.0),
            ("auth", 1.5),
        ),
    ),
    Rule(
        "Dev-Tools/Software-Archives",
        (
            ("installer", 3.0),
            ("archive", 2.0),
            ("dmg", 3.0),
            ("vlc", 4.0),
        ),
    ),
    Rule(
        "Finance/Taxes",
        (
            ("tax return", 5.0),
            ("tax", 3.0),
            ("irs", 4.0),
            ("w-2", 4.0),
            ("1099", 4.0),
            ("property tax", 4.0),
        ),
    ),
    Rule(
        "Finance/Investments",
        (
            ("portfolio", 5.0),
            ("positions", 4.5),
            ("brokerage", 4.5),
            ("fidelity", 4.0),
            ("vanguard", 4.0),
            ("401k", 5.0),
            ("ira", 4.0),
            ("roth", 4.0),
            ("pension", 4.0),
            ("investment", 3.5),
            ("dividend", 3.0),
            ("balance", 2.0),
        ),
    ),
    Rule(
        "Finance/Mortgage",
        (
            ("mortgage", 5.0),
            ("deed", 4.0),
            ("escrow", 4.0),
            ("hoa", 3.0),
            ("home insurance", 3.0),
            ("property", 1.0),
        ),
    ),
    Rule(
        "Finance/Banking",
        (
            ("bank", 3.0),
            ("checking", 4.0),
            ("savings", 4.0),
            ("wire", 2.5),
            ("deposit", 2.5),
            ("withdrawal", 2.5),
            ("statement", 2.5),
            ("account", 2.0),
        ),
    ),
    Rule(
        "Business/Client-Work",
        (
            ("client brief", 5.0),
            ("client", 3.0),
            ("invoice", 3.0),
            ("proposal", 4.0),
            ("statement of work", 5.0),
            ("sow", 3.5),
            ("rebrand", 4.0),
            ("campaign", 3.5),
            ("brief", 2.5),
        ),
    ),
    Rule(
        "Business/Pitch-Decks",
        (
            ("pitch deck", 5.0),
            ("pitch", 3.0),
            ("deck", 3.0),
            ("slides", 3.0),
            ("presentation", 3.0),
            ("investor", 3.0),
        ),
    ),
    Rule(
        "Business/Branding",
        (
            ("branding", 5.0),
            ("brand", 4.0),
            ("logo", 4.0),
            ("style guide", 4.0),
            ("pantone", 4.0),
            ("mockup", 3.5),
            ("figma", 3.0),
            ("dribbble", 3.0),
        ),
    ),
    Rule(
        "Kids/School",
        (
            ("report card", 5.0),
            ("school", 3.0),
            ("worksheet", 3.5),
            ("math worksheet", 5.0),
            ("art class", 4.0),
            ("pickup", 3.0),
            ("student", 3.0),
        ),
    ),
    Rule(
        "Kids/Health",
        (
            ("vaccination", 4.0),
            ("immunization", 4.0),
            ("pediatric", 4.0),
        ),
    ),
    Rule(
        "Health/Medical",
        (
            ("blood test", 5.0),
            ("lab result", 5.0),
            ("prescription", 4.0),
            ("doctor", 3.0),
            ("referral", 3.0),
            ("medicare", 4.0),
            ("medical", 3.0),
        ),
    ),
    Rule(
        "Identity/Driver-License",
        (
            ("driver license", 6.0),
            ("class c", 3.0),
            ("endorsement", 3.0),
            ("restriction", 3.0),
            ("license", 2.5),
            ("dl ", 2.0),
        ),
    ),
    Rule(
        "Identity/Passport",
        (
            ("passport", 5.0),
            ("visa", 3.0),
            ("travel document", 3.0),
        ),
    ),
    Rule(
        "Family/Trips",
        (
            ("hotel", 3.0),
            ("cruise", 4.0),
            ("reservation", 3.0),
            ("tickets", 3.0),
            ("trip", 3.0),
            ("travel", 2.0),
        ),
    ),
    Rule(
        "Family/Housing",
        (
            ("lease", 4.0),
            ("hoa", 3.0),
            ("rent", 3.0),
            ("moving", 2.0),
            ("home sale", 4.0),
        ),
    ),
    Rule(
        "Home/Manuals",
        (
            ("manual", 4.0),
            ("installation", 3.0),
            ("warranty", 3.0),
            ("hvac", 4.0),
            ("roof", 3.0),
            ("appliance", 3.0),
        ),
    ),
    Rule(
        "Home/Hardware",
        (
            ("hardware", 3.0),
            ("repair", 2.0),
            ("maintenance", 2.5),
            ("inspection", 2.5),
            ("title", 2.0),
        ),
    ),
    Rule(
        "Music/AI-Songs",
        (
            ("made with suno", 6.0),
            ("suno", 5.0),
            ("song", 3.0),
            ("lyrics", 3.0),
            ("track", 2.0),
            ("album", 2.0),
        ),
        kind_bonus={"audio": 1.0},
    ),
    Rule(
        "AI-Art/Book-Covers",
        (
            ("generated image", 4.0),
            ("gemini", 4.0),
            ("midjourney", 4.0),
            ("stable diffusion", 4.0),
            ("book cover", 5.0),
            ("cover art", 4.0),
            ("prompt", 2.0),
            ("illustration", 2.0),
        ),
        kind_bonus={"image": 1.0},
    ),
    Rule(
        "AI-Art/Visual-Assets",
        (
            ("generated", 4.0),
            ("create", 2.0),
            ("illustration", 3.0),
            ("artwork", 3.0),
            ("character", 2.0),
            ("render", 2.5),
            ("dall-e", 5.0),
            ("dalle", 5.0),
            ("midjourney", 5.0),
            ("stable diffusion", 4.5),
            ("gemini", 4.5),
            ("clip", 2.0),
        ),
        kind_bonus={"video": 1.0, "image": 1.0},
    ),
    Rule(
        "AI-Art/Prompts-Workflows",
        (
            ("prompt", 4.0),
            ("workflow", 3.5),
            ("cfg", 2.0),
            ("sampler", 2.0),
            ("steps", 1.5),
            ("seed", 1.5),
            ("scheduler", 1.5),
            ("negative", 1.5),
            ("controlnet", 2.5),
        ),
        kind_bonus={"json": 1.0},
    ),
    Rule(
        "Projects/MediaOps",
        (
            ("mediaops", 6.0),
            ("upload", 3.0),
            ("metadata", 3.0),
            ("playlists", 3.0),
            ("delete", 3.0),
            ("lolcow", 3.0),
            ("walkthrough", 2.5),
            ("screen recording", 4.0),
            ("recording", 2.0),
            ("chrome", 1.5),
            ("webm", 1.5),
        ),
        kind_bonus={"video": 1.0},
    ),
    Rule(
        "Projects/Code",
        (
            ("package.json", 5.0),
            ("package-lock.json", 4.5),
            ("pyproject.toml", 4.5),
            ("go.mod", 4.5),
            ("cargo.toml", 4.5),
            ("requirements.txt", 4.0),
            ("setup.py", 4.0),
            ("makefile", 4.0),
            ("readme.md", 2.5),
            (".gitignore", 3.5),
            ("src/", 4.0),
            ("node_modules", 4.0),
            ("tsconfig", 4.0),
            ("build", 2.5),
            ("bundle", 2.5),
            ("playground", 2.0),
            ("prototype", 2.0),
        ),
    ),
    Rule(
        "Projects",
        (
            ("screenshot", 3.0),
            ("screen recording", 4.0),
            ("demo", 2.5),
            ("walkthrough", 2.5),
            ("prototype", 2.5),
            ("recording", 1.5),
        ),
        kind_bonus={"video": 1.0},
    ),
    Rule(
        "Reading/Papers",
        (
            ("paper", 3.0),
            ("research", 3.0),
            ("article", 2.5),
            ("essay", 2.0),
            ("study", 2.0),
        ),
    ),
    Rule(
        "Photos",
        (
            ("img_", 3.0),
            ("dcim", 3.0),
            ("dsc", 3.0),
            ("photo", 2.5),
            ("snapshot", 2.0),
            ("camera", 2.0),
        ),
        kind_bonus={"image": 1.5},
    ),
)

SENSITIVE_PATTERNS = (
    "client_secret",
    "api_key",
    "apikey",
    "token",
    "password",
    "private key",
    "begin private key",
    "oauth",
    "credential",
    "proxy",
    "session required",
)


@dataclass
class FileEvidence:
    path: str
    kind: str
    mime: str
    size: int
    mtime: str
    sources: dict[str, str]
    metadata: dict[str, Any]
    notes: list[str]
    tokens: list[str]


@dataclass
class FileRecord:
    path: str
    kind: str
    mime: str
    size: int
    mtime: str
    sources: dict[str, str]
    metadata: dict[str, Any]
    top_candidates: list[dict[str, Any]]
    suggested_home: str | None
    taxonomy_hints: list[dict[str, Any]]
    final_home: str | None
    placement_mode: str
    confidence: float
    needs_refinement: bool
    flags: list[str]
    tokens: list[str]


def run_tool(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        return 127, "", f"missing tool: {args[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout: {' '.join(args)}"


def tool_exists(name: str) -> bool:
    return shutil.which(name) is not None


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
        return value[1:-1]
    return value


PATTERN_REGEX_CACHE: dict[str, re.Pattern[str]] = {}


def pattern_regex(pattern: str) -> re.Pattern[str]:
    cached = PATTERN_REGEX_CACHE.get(pattern)
    if cached is not None:
        return cached

    escaped = re.escape(pattern.lower())
    if pattern and pattern[-1] in "/._-+":
        expr = rf"(?<![a-z0-9]){escaped}"
    else:
        expr = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
    compiled = re.compile(expr)
    PATTERN_REGEX_CACHE[pattern] = compiled
    return compiled


def pattern_in_text(pattern: str, text: str) -> bool:
    if not pattern or not text:
        return False
    return bool(pattern_regex(pattern).search(text))


def flatten_text_values(value: Any, limit: int = 400) -> list[str]:
    if value is None:
        return []
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", errors="ignore")
        except Exception:
            value = value.decode(errors="ignore")
    if isinstance(value, dict):
        parts: list[str] = []
        for item in value.values():
            parts.extend(flatten_text_values(item, limit=limit))
        return parts
    if isinstance(value, (list, tuple, set)):
        parts: list[str] = []
        for item in value:
            parts.extend(flatten_text_values(item, limit=limit))
        return parts
    text = str(value).strip()
    if not text:
        return []
    return [text[:limit]]


def text_value(value: Any, limit: int = 400) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", errors="ignore")
        except Exception:
            value = value.decode(errors="ignore")
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            item_text = text_value(item, limit)
            if item_text:
                parts.append(f"{key}={item_text}")
        return "; ".join(parts)[:limit]
    if isinstance(value, (list, tuple, set)):
        parts = [text_value(item, limit) for item in value]
        parts = [part for part in parts if part]
        return "; ".join(parts)[:limit]
    return str(value).strip()[:limit]


def slugify(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-")
    return value or "item"


def detect_kind(path: Path, mime: str) -> str:
    ext = path.suffix.lower()
    if ext in PDF_EXTS or mime == "application/pdf":
        return "pdf"
    if ext in DOCX_EXTS:
        return "docx"
    if ext in PPTX_EXTS:
        return "pptx"
    if ext in XLSX_EXTS:
        return "xlsx"
    if ext in OLD_OFFICE_EXTS:
        return "legacy-office"
    if ext in CSV_EXTS:
        return "csv"
    if ext in JSON_EXTS:
        return "json"
    if ext in IMAGE_EXTS or (mime or "").startswith("image/"):
        return "image"
    if ext in VIDEO_EXTS or (mime or "").startswith("video/"):
        return "video"
    if ext in AUDIO_EXTS or (mime or "").startswith("audio/"):
        return "audio"
    if ext in TEXT_EXTS or (mime or "").startswith("text/"):
        return "text"
    if ext in {".zip", ".dmg", ".tar", ".gz", ".bz2", ".xz", ".7z"}:
        return "archive"
    return "binary"


def mime_type(path: Path) -> str:
    if tool_exists("file"):
        code, out, _ = run_tool(["file", "--mime-type", "-b", str(path)], timeout=15)
        if code == 0:
            return out.strip()
    guess, _ = mimetypes.guess_type(path.name)
    return guess or "application/octet-stream"


def file_brief(path: Path) -> str:
    if tool_exists("file"):
        code, out, _ = run_tool(["file", "-b", str(path)], timeout=15)
        if code == 0:
            return out.strip()
    return ""


def read_text_preview(path: Path, max_lines: int = 20, max_chars: int = 4000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    lines = text.splitlines()
    preview = "\n".join(lines[:max_lines])
    return preview[:max_chars]


def extract_pdf_preview(path: Path) -> str:
    if PdfReader is not None:
        try:
            reader = PdfReader(str(path))
            pieces: list[str] = []
            metadata = getattr(reader, "metadata", None)
            if metadata:
                meta_bits = []
                for key, value in metadata.items():
                    value_text = text_value(value, 250)
                    if value_text:
                        meta_bits.append(f"{key}:{value_text}")
                if meta_bits:
                    pieces.append(" ".join(meta_bits))
            for page in reader.pages[:2]:
                page_text = page.extract_text() or ""
                if page_text:
                    pieces.append(page_text)
            preview = "\n".join(pieces).strip()
            if preview:
                return preview[:5000]
        except Exception:
            pass
    if not tool_exists("pdftotext"):
        return ""
    code, out, _ = run_tool(["pdftotext", "-l", "2", str(path), "-"], timeout=30)
    if code == 0:
        return out.strip()[:5000]
    return ""


def extract_image_metadata(path: Path) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if Image is None:
        return metadata

    try:
        with Image.open(path) as img:
            if img.format:
                metadata["format"] = img.format
            if img.mode:
                metadata["mode"] = img.mode
            if getattr(img, "width", None) is not None and getattr(img, "height", None) is not None:
                metadata["dimensions"] = f"{img.width}x{img.height}"

            info = getattr(img, "info", {}) or {}
            for key, value in info.items():
                if key == "icc_profile":
                    continue
                text = text_value(value, 300)
                if text:
                    metadata[f"pil_{slugify(str(key)).lower()}"] = text

            exif = getattr(img, "getexif", lambda: {})()
            if exif:
                for tag_id, value in exif.items():
                    tag_name = PIL_EXIF_TAGS.get(tag_id, str(tag_id))
                    text = text_value(value, 300)
                    if text:
                        metadata[f"exif_{slugify(str(tag_name)).lower()}"] = text
    except Exception:
        return metadata

    return metadata


def extract_docx_preview(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            with zf.open("word/document.xml") as fh:
                root = ET.fromstring(fh.read())
        text = " ".join(t.strip() for t in root.itertext() if t and t.strip())
        return text[:5000]
    except Exception:
        return ""


def extract_pptx_preview(path: Path) -> str:
    texts: list[str] = []
    try:
        with zipfile.ZipFile(path) as zf:
            slide_names = sorted(name for name in zf.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml"))
            for name in slide_names[:6]:
                with zf.open(name) as fh:
                    root = ET.fromstring(fh.read())
                slide_text = " ".join(t.strip() for t in root.itertext() if t and t.strip())
                if slide_text:
                    texts.append(slide_text)
    except Exception:
        return ""
    return "\n".join(texts)[:5000]


def extract_xlsx_preview(path: Path) -> str:
    try:
        import openpyxl  # type: ignore

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows: list[str] = []
        for idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
            values = ["" if cell is None else str(cell) for cell in row[:12]]
            rows.append(", ".join(values))
            if idx >= 8:
                break
        wb.close()
        return "\n".join(rows)[:5000]
    except Exception:
        pass

    try:
        with zipfile.ZipFile(path) as zf:
            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in zf.namelist():
                with zf.open("xl/sharedStrings.xml") as fh:
                    root = ET.fromstring(fh.read())
                for node in root.iter():
                    if node.tag.endswith("}t") and node.text:
                        shared_strings.append(node.text)

            sheet_name = "xl/worksheets/sheet1.xml"
            if sheet_name not in zf.namelist():
                return ""
            with zf.open(sheet_name) as fh:
                root = ET.fromstring(fh.read())

            rows: list[str] = []
            for row in root.iter():
                if not row.tag.endswith("}row"):
                    continue
                cells: list[str] = []
                for cell in row:
                    if not cell.tag.endswith("}c"):
                        continue
                    cell_type = cell.attrib.get("t", "")
                    value = ""
                    for child in cell:
                        if child.tag.endswith("}v") and child.text:
                            if cell_type == "s":
                                try:
                                    value = shared_strings[int(child.text)]
                                except Exception:
                                    value = child.text
                            else:
                                value = child.text
                        elif child.tag.endswith("}is"):
                            value = " ".join(t.text or "" for t in child.iter() if t.text)
                    cells.append(value)
                if cells:
                    rows.append(", ".join(cells))
                if len(rows) >= 8:
                    break
            return "\n".join(rows)[:5000]
    except Exception:
        return ""

    return ""


def extract_csv_preview(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as fh:
            reader = csv.reader(fh)
            rows = []
            for idx, row in enumerate(reader, start=1):
                rows.append(", ".join(cell.strip() for cell in row[:12]))
                if idx >= 8:
                    break
        return "\n".join(rows)[:5000]
    except Exception:
        return ""


def summarize_json_payload(value: Any, prefix: str = "", limit: int = 40) -> list[str]:
    if limit <= 0:
        return []
    if isinstance(value, dict):
        rows: list[str] = []
        for key, item in list(value.items())[:limit]:
            label = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(item, (dict, list)):
                rows.append(label)
                rows.extend(summarize_json_payload(item, prefix=label, limit=max(limit - len(rows), 0)))
            else:
                item_text = text_value(item, 120)
                rows.append(f"{label}: {item_text}" if item_text else label)
            if len(rows) >= limit:
                break
        return rows[:limit]
    if isinstance(value, list):
        rows: list[str] = []
        for idx, item in enumerate(value[: min(len(value), limit)], start=1):
            label = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
            if isinstance(item, (dict, list)):
                rows.append(label)
                rows.extend(summarize_json_payload(item, prefix=label, limit=max(limit - len(rows), 0)))
            else:
                item_text = text_value(item, 120)
                rows.append(f"{label}: {item_text}" if item_text else label)
            if len(rows) >= limit:
                break
        return rows[:limit]
    leaf = text_value(value, 120)
    return [f"{prefix}: {leaf}" if prefix else leaf] if leaf else []


def extract_json_preview(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return read_text_preview(path)
    return "\n".join(summarize_json_payload(data))[:5000]


def extract_old_office_preview(path: Path) -> str:
    if tool_exists("antiword"):
        code, out, _ = run_tool(["antiword", str(path)], timeout=30)
        if code == 0:
            return out.strip()[:5000]
    if tool_exists("strings"):
        code, out, _ = run_tool(["strings", str(path)], timeout=15)
        if code == 0:
            return "\n".join(out.splitlines()[:30])[:5000]
    return ""


def parse_mdls(path: Path) -> dict[str, str]:
    if not tool_exists("mdls"):
        return {}
    code, out, _ = run_tool(["mdls", str(path)], timeout=15)
    if code != 0:
        return {}
    parsed: dict[str, str] = {}
    for line in out.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = strip_quotes(value.strip())
        if value and value != "(null)":
            parsed[key] = value
    return parsed


def parse_ffprobe(path: Path) -> dict[str, Any]:
    if not tool_exists("ffprobe"):
        return {}
    args = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    code, out, _ = run_tool(args, timeout=30)
    if code != 0:
        return {}
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {}

    result: dict[str, Any] = {}
    fmt = data.get("format") or {}
    if fmt:
        result["format_name"] = fmt.get("format_name")
        result["duration"] = fmt.get("duration")
        if fmt.get("tags"):
            result["tags"] = fmt["tags"]
        if fmt.get("filename"):
            result["filename"] = Path(fmt["filename"]).name

    streams = data.get("streams") or []
    if streams:
        compact_streams = []
        for stream in streams[:4]:
            compact = {}
            for key in ("codec_type", "codec_name", "width", "height", "channels", "sample_rate", "bit_rate"):
                if stream.get(key) is not None:
                    compact[key] = stream.get(key)
            if stream.get("tags"):
                compact["tags"] = stream["tags"]
            if compact:
                compact_streams.append(compact)
        if compact_streams:
            result["streams"] = compact_streams
    return result


def parse_mutagen_media(path: Path) -> dict[str, Any]:
    if mutagen is None:
        return {}

    try:
        media = mutagen.File(str(path), easy=False)
    except Exception:
        return {}

    if media is None:
        return {}

    result: dict[str, Any] = {"format_name": media.__class__.__name__}

    tags = getattr(media, "tags", None)
    if tags:
        normalized_tags: dict[str, str] = {}
        try:
            for key, value in tags.items():
                text = text_value(value, 500)
                if text:
                    normalized_tags[str(key)] = text
        except Exception:
            normalized_tags = {}
        if normalized_tags:
            result["tags"] = normalized_tags

    info = getattr(media, "info", None)
    if info:
        normalized_info: dict[str, Any] = {}
        for key in ("length", "bitrate", "sample_rate", "channels", "width", "height"):
            value = getattr(info, key, None)
            if value is not None:
                normalized_info[key] = value
        if normalized_info:
            result["info"] = normalized_info

    return result


def extract_image_ocr(path: Path) -> str:
    if not tool_exists("tesseract"):
        return ""
    try:
        with Image.open(path) as image:
            width, height = image.size
        if width * height > IMAGE_OCR_MAX_PIXELS:
            return ""
    except Exception:
        pass
    with tempfile.TemporaryDirectory(prefix="tidy_scan_") as tmpdir:
        outbase = Path(tmpdir) / "ocr"
        code, _, _ = run_tool(
            ["tesseract", str(path), str(outbase), "--psm", "6"],
            timeout=IMAGE_OCR_TIMEOUT_SECONDS,
        )
        txt_path = outbase.with_suffix(".txt")
        if code == 0 and txt_path.exists():
            try:
                return txt_path.read_text(encoding="utf-8", errors="ignore").strip()[:5000]
            except Exception:
                return ""
    return ""


VISION_PIPELINE: Any | None = None
VISION_PIPELINE_MODE: str | None = None
VISION_PROVIDER: str = "hf"
VISION_PROVIDER_MODEL: str = ""


def vision_pipeline() -> Any | None:
    global VISION_PIPELINE
    global VISION_PIPELINE_MODE

    if VISION_PIPELINE is not None or hf_pipeline is None:
        return VISION_PIPELINE

    for model in VISION_MODELS:
        try:
            VISION_PIPELINE = hf_pipeline("image-to-text", model=model)
            VISION_PIPELINE_MODE = "image-to-text"
            return VISION_PIPELINE
        except Exception:
            VISION_PIPELINE = None
            VISION_PIPELINE_MODE = None
            continue

    # Newer transformers builds expose BLIP captioning under `image-text-to-text`.
    for model in VISION_MODELS:
        try:
            VISION_PIPELINE = hf_pipeline("image-text-to-text", model=model)
            VISION_PIPELINE_MODE = "image-text-to-text"
            return VISION_PIPELINE
        except Exception:
            VISION_PIPELINE = None
            VISION_PIPELINE_MODE = None
            continue

    return None


def set_vision_provider(provider: str, model: str = "") -> None:
    global VISION_PROVIDER
    global VISION_PROVIDER_MODEL

    VISION_PROVIDER = provider
    VISION_PROVIDER_MODEL = (model or "").strip()


def ensure_local_vision_runtime(argv: list[str]) -> None:
    if VISION_PROVIDER == "openai" or hf_pipeline is not None:
        return
    if os.getenv(LOCAL_VISION_BOOTSTRAP_ENV) == "1":
        return

    uv_path = shutil.which("uv")
    if uv_path is None:
        return

    env = os.environ.copy()
    env[LOCAL_VISION_BOOTSTRAP_ENV] = "1"
    script_path = str(Path(__file__).resolve())
    os.execvpe(
        uv_path,
        [
            uv_path,
            "run",
            "--with",
            "transformers>=4.41",
            "--with",
            "torch",
            "--with",
            "torchvision",
            script_path,
            *argv[1:],
        ],
        env,
    )


def resolve_vision_model() -> str:
    if VISION_PROVIDER != "openai":
        return ""

    return VISION_PROVIDER_MODEL or os.getenv("OPENAI_VISION_MODEL", OPENAI_VISION_MODEL)


def extract_image_vision_caption_openai(path: Path, max_chars: int = 5000) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return ""

    try:
        mime, _ = mimetypes.guess_type(path.as_posix())
        mime = mime or "image/png"
        image_bytes = path.read_bytes()
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": resolve_vision_model(),
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Describe this image for file organization in one short sentence.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                        },
                    ],
                }
            ],
            "max_tokens": 96,
        }
        request = urllib.request.Request(
            OPENAI_CHAT_COMPLETIONS_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
        )
        request.add_header("Authorization", f"Bearer {api_key}")
        request.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return ""

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""

    message = choices[0].get("message", {})
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()[:max_chars]
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text") or part.get("content")
                if isinstance(text, str):
                    parts.append(text)
        if parts:
            return " ".join(parts).strip()[:max_chars]
    return ""


def _vision_output_to_text(output: Any) -> str:
    if isinstance(output, str):
        return output.strip()

    if isinstance(output, dict):
        for key in ("generated_text", "text", "caption", "output_text"):
            value = output.get(key, "")
            if value:
                return str(value).strip()
        return ""

    if isinstance(output, (list, tuple)):
        for item in output:
            text = _vision_output_to_text(item)
            if text:
                return text

    return ""


def extract_image_vision_caption(path: Path, max_chars: int = 5000) -> str:
    if VISION_PROVIDER == "openai":
        return extract_image_vision_caption_openai(path, max_chars=max_chars)

    pipe = vision_pipeline()
    if pipe is None:
        return ""

    try:
        if VISION_PIPELINE_MODE == "image-text-to-text":
            outputs = pipe(
                {
                    "images": [str(path)],
                    "text": "Describe this image for file organization in one short sentence.",
                },
                max_new_tokens=64,
            )
        else:
            outputs = pipe(str(path), max_new_tokens=64)

        text = _vision_output_to_text(outputs)
        if not text:
            return ""
        return str(text).strip()[:max_chars]
    except Exception:
        return ""


def media_files_for_vision_check(paths: list[Path]) -> list[tuple[Path, str]]:
    media_files: list[tuple[Path, str]] = []
    for path in paths:
        if not path.is_file():
            continue
        kind = detect_kind(path, mime_type(path))
        if kind in {"image", "video"}:
            media_files.append((path, kind))
    return media_files


def validate_vision_readiness(paths: list[Path]) -> tuple[bool, dict[str, Any]]:
    media_files = media_files_for_vision_check(paths)
    media_kinds = sorted({kind for _, kind in media_files})

    if not media_kinds:
        return (
            True,
            {
                "enabled": False,
                "status": "skipped_no_media",
                "reason": "No image or video files were found for visual analysis in this scope.",
            },
        )

    if VISION_PROVIDER == "openai" and not os.getenv("OPENAI_API_KEY"):
        return (
            False,
            {
                "enabled": True,
                "status": "provider_unavailable",
                "reason": "OpenAI vision provider was selected but OPENAI_API_KEY is not set.",
            },
        )

    if VISION_PROVIDER != "openai" and vision_pipeline() is None:
        return (
            False,
            {
                "enabled": True,
                "status": "pipeline_unavailable",
                "reason": "Vision pipeline could not be initialized for image/video captioning.",
            },
        )

    if "video" in media_kinds and not tool_exists("ffmpeg"):
        return (
            False,
            {
                "enabled": True,
                "status": "missing_tool",
                "reason": "Video vision analysis requires ffmpeg to sample frames.",
            },
        )

    return (
        True,
        {
            "enabled": True,
            "status": "ready",
            "details": {
                "provider": VISION_PROVIDER,
                "model": resolve_vision_model() if VISION_PROVIDER == "openai" else "local-hf",
                "media_kinds": media_kinds,
                "file_count": len(media_files),
            },
        },
    )


def extract_video_frame_ocr(path: Path, metadata: dict[str, Any]) -> str:
    if not tool_exists("ffmpeg") or not tool_exists("tesseract"):
        return ""

    duration = 0.0
    try:
        duration = float(metadata.get("duration") or 0.0)
    except Exception:
        duration = 0.0
    frames: list[str] = []
    if duration <= 0:
        offsets = (0.5,)
    else:
        offsets = VIDEO_FRAME_SAMPLE_OFFSETS

    with tempfile.TemporaryDirectory(prefix="tidy_scan_") as tmpdir:
        for idx, factor in enumerate(offsets, start=1):
            if duration <= 0:
                sample_at = 0.5
            else:
                sample_at = max(min(duration * factor, max(duration - 0.05, 0.05)), 0.05)
            frame_path = Path(tmpdir) / f"frame_{idx}.png"
            args = [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{sample_at:.2f}",
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-f",
                "image2",
                "-update",
                "1",
                str(frame_path),
            ]
            code, _, _ = run_tool(args, timeout=VIDEO_FRAME_OCR_TIMEOUT_SECONDS)
            if code == 0 and frame_path.exists():
                text = extract_image_ocr(frame_path)
                if text:
                    frames.append(text)
            if len(frames) >= 2:
                break
        if frames:
            return " ".join(frames)[:5000]
    return ""


def extract_video_frame_vision(path: Path, metadata: dict[str, Any]) -> str:
    if not tool_exists("ffmpeg"):
        return ""

    duration = 0.0
    try:
        duration = float(metadata.get("duration") or 0.0)
    except Exception:
        duration = 0.0

    if duration <= 0:
        offsets = (0.5,)
    else:
        offsets = VIDEO_FRAME_SAMPLE_OFFSETS

    lines: list[str] = []
    if VISION_PROVIDER != "openai" and vision_pipeline() is None:
        return ""

    with tempfile.TemporaryDirectory(prefix="tidy_scan_") as tmpdir:
        for idx, factor in enumerate(offsets, start=1):
            if duration <= 0:
                sample_at = 0.5
            else:
                sample_at = max(min(duration * factor, max(duration - 0.05, 0.05)), 0.05)
            frame_path = Path(tmpdir) / f"vision_frame_{idx}.png"
            args = [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{sample_at:.2f}",
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-f",
                "image2",
                "-update",
                "1",
                str(frame_path),
            ]
            code, _, _ = run_tool(args, timeout=60)
            if code != 0 or not frame_path.exists():
                continue
            caption = extract_image_vision_caption(frame_path)
            if caption:
                lines.append(caption)
            if len(lines) >= 2:
                break
    if lines:
        return " ".join(lines)[:5000]
    return ""


def extract_sources(
    path: Path,
    root: Path,
    kind: str,
    mime: str,
    *,
    vision_enabled: bool = False,
) -> tuple[dict[str, str], dict[str, Any], list[str]]:
    try:
        relative_path = path.relative_to(root).as_posix().lower()
    except ValueError:
        relative_path = path.name.lower()

    sources: dict[str, str] = {"path": relative_path, "name": path.name.lower()}
    metadata: dict[str, Any] = {}
    notes: list[str] = []

    brief = file_brief(path)
    if brief:
        sources["file"] = brief.lower()

    if kind == "pdf":
        text = extract_pdf_preview(path)
        if text:
            sources["text"] = text.lower()
        else:
            notes.append("no_pdf_text")
    elif kind == "docx":
        text = extract_docx_preview(path)
        if text:
            sources["text"] = text.lower()
        else:
            notes.append("no_docx_text")
    elif kind == "pptx":
        text = extract_pptx_preview(path)
        if text:
            sources["text"] = text.lower()
        else:
            notes.append("no_pptx_text")
    elif kind == "xlsx":
        text = extract_xlsx_preview(path)
        if text:
            sources["text"] = text.lower()
        else:
            notes.append("no_xlsx_text")
    elif kind == "text":
        text = read_text_preview(path)
        if text:
            sources["text"] = text.lower()
    elif kind == "csv":
        text = extract_csv_preview(path)
        if text:
            sources["text"] = text.lower()
    elif kind == "json":
        text = extract_json_preview(path)
        if text:
            sources["text"] = text.lower()
        else:
            notes.append("no_json_text")
    elif kind == "legacy-office":
        text = extract_old_office_preview(path)
        if text:
            sources["text"] = text.lower()
        else:
            notes.append("legacy_office_unreadable")
    elif kind == "image":
        metadata = parse_mdls(path)
        if metadata:
            metadata = {
                key: value
                for key, value in metadata.items()
                if key in MDLS_CONTENT_FIELDS
            }
        image_metadata = extract_image_metadata(path)
        if image_metadata:
            metadata.update(image_metadata)
        ocr = extract_image_ocr(path)
        if ocr:
            sources["ocr"] = ocr.lower()
        else:
            notes.append("no_image_ocr")
        if vision_enabled:
            vision = extract_image_vision_caption(path)
            if vision:
                sources["vision"] = vision.lower()
            else:
                notes.append("no_image_vision")
    elif kind in {"video", "audio"}:
        metadata = parse_ffprobe(path)
        fallback_metadata = parse_mutagen_media(path)
        for key, value in fallback_metadata.items():
            metadata.setdefault(key, value)
        if metadata:
            metadata["kind"] = kind
        if kind == "video":
            ocr = extract_video_frame_ocr(path, metadata)
            if ocr:
                sources["ocr"] = ocr.lower()
            else:
                notes.append("no_video_ocr")
            if vision_enabled:
                vision = extract_video_frame_vision(path, metadata)
                if vision:
                    sources["vision"] = vision.lower()
                else:
                    notes.append("no_video_vision")
    elif kind == "archive":
        notes.append("archive_unreadable")

    if metadata:
        metadata_text = " ".join(flatten_text_values(metadata, limit=5000))[:5000]
        if metadata_text:
            sources["metadata"] = metadata_text.lower()

    if not metadata and kind in {"image", "video", "audio"}:
        notes.append("metadata_limited")
    return sources, metadata, notes


def contains_any(text: str, patterns: Iterable[str]) -> list[str]:
    hits: list[str] = []
    for pat in patterns:
        if pat in text:
            hits.append(pat)
    return hits


def is_meaningful_taxonomy_segment(segment: str) -> bool:
    tokens = {token for token in TOKEN_RE.findall(segment.lower()) if token}
    if not tokens:
        return False
    return any(token not in GENERIC_TAXONOMY_SEGMENTS for token in tokens)


def is_project_internal_segment(segment: str) -> bool:
    normalized = slugify(segment).lower()
    return normalized in PROJECT_INTERNAL_SEGMENTS


def collect_existing_taxonomy_hints(
    paths: list[Path], root: Path, max_depth: int = TAXONOMY_HINT_MAX_DEPTH
) -> dict[str, tuple[str, float, int]]:
    raw_counts: Counter[str] = Counter()
    marker_counts: Counter[str] = Counter()
    canonical_by_key: dict[str, str] = {}

    for path in paths:
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        parts = rel.parts
        if len(parts) < 2:
            continue

        ancestor_parts = parts[:-1]
        for depth in range(1, min(len(ancestor_parts), max_depth) + 1):
            candidate_parts = ancestor_parts[:depth]
            if any(part.lower() in PRODUCTION_MODE_TAXONOMY_BLACKLIST for part in candidate_parts):
                continue
            if any(is_project_internal_segment(part) for part in candidate_parts):
                continue
            if not is_meaningful_taxonomy_segment(candidate_parts[-1]):
                continue
            key = "/".join(part.lower() for part in candidate_parts)
            raw_counts[key] += 1
            canonical_by_key.setdefault(key, "/".join(candidate_parts))

        if path.name.lower() in PROJECT_MARKER_FILES:
            key = "/".join(part.lower() for part in ancestor_parts)
            if key:
                marker_counts[key] += 1

    hints: dict[str, tuple[str, float, int]] = {}
    for key, count in raw_counts.items():
        if not is_meaningful_taxonomy_segment(key):
            continue
        if count < TAXONOMY_HINT_MIN_FILES and marker_counts[key] == 0:
            continue

        base = min(6.0, 1.2 + (count * 0.55))
        if marker_counts[key]:
            base = min(6.8, base + 1.5)
        hints[key] = (canonical_by_key.get(key, key), round(base, 2), count + marker_counts[key])

    # Keep the most specific hints first to avoid ancestor/descendant collisions
    # that can dilute confidence (e.g. 3D-Printing and 3D-Printing/Models).
    ordered_keys = sorted(hints.keys(), key=lambda key: key.count("/"), reverse=True)
    pruned_hints: dict[str, tuple[str, float, int]] = {}
    for key in ordered_keys:
        if any(existing.startswith(f"{key}/") for existing in pruned_hints):
            continue
        pruned_hints[key] = hints[key]

    if pruned_hints:
        return dict(sorted(pruned_hints.items(), key=lambda item: item[1][1], reverse=True))

    return dict(sorted(hints.items(), key=lambda item: item[1][1], reverse=True))


def collect_refinement_hints(
    records: list[FileRecord],
    root: Path,
    min_confidence: float = AUTOPILOT_REFINEMENT_MIN_CONFIDENCE,
    min_support: int = AUTOPILOT_REFINEMENT_MIN_SUPPORT,
    min_ratio: float = AUTOPILOT_REFINEMENT_MIN_RATIO,
    max_depth: int = TAXONOMY_HINT_MAX_DEPTH,
) -> dict[str, tuple[str, float, int]]:
    home_support: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for rec in records:
        if rec.needs_refinement or rec.confidence < min_confidence:
            continue
        if not rec.final_home:
            continue

        try:
            rel = Path(rec.path).relative_to(root)
        except ValueError:
            continue

        ancestors = rel.parts[:-1]
        if not ancestors:
            continue

        for depth in range(1, min(len(ancestors), max_depth) + 1):
            key = "/".join(part.lower() for part in ancestors[:depth])
            home_support[key][rec.final_home] += 1

    hints: dict[str, tuple[str, float, int]] = {}
    for key, homes in home_support.items():
        if not homes:
            continue
        sorted_homes = homes.most_common()
        top_home, top_support = sorted_homes[0]
        total = sum(homes.values())
        if total < min_support:
            continue
        if (top_support / total) < min_ratio:
            continue
        if total == 0:
            continue
        score = min(6.5, 1.4 + (top_support * 0.6) + (top_support / max(total, 1)))
        hints[key] = (top_home, round(score, 2), int(top_support))
    return hints


def merge_taxonomy_hints(
    base_hints: dict[str, tuple[str, float, int]],
    added_hints: dict[str, tuple[str, float, int]],
) -> dict[str, tuple[str, float, int]]:
    merged = dict(base_hints)
    for key, (home, score, support) in added_hints.items():
        existing = merged.get(key)
        if existing is None:
            merged[key] = (home, score, support)
            continue

        existing_home, existing_score, existing_support = existing
        if existing_home == home:
            merged[key] = (home, round(existing_score + score, 2), existing_support + support)
            continue

        if score > existing_score + 0.7:
            merged[key] = (home, score, support)

    return merged


def infer_taxonomy_hints(
    path: Path, root: Path, taxonomy_hints: dict[str, tuple[str, float, int]]
) -> list[dict[str, Any]]:
    if not taxonomy_hints:
        return []

    try:
        rel = path.relative_to(root)
    except ValueError:
        return []

    ancestors = rel.parts[:-1]
    if not ancestors:
        return []

    hits: dict[str, dict[str, float]] = {}
    for depth in range(1, min(len(ancestors), TAXONOMY_HINT_MAX_DEPTH) + 1):
        key = "/".join(part.lower() for part in ancestors[:depth])
        hint = taxonomy_hints.get(key)
        if hint is None:
            continue
        canonical_home, weight, support = hint
        # deeper taxonomy context is usually more specific
        weighted = weight + (depth * 0.25)
        existing = hits.get(canonical_home)
        if existing is None or weighted > existing["weight"]:
            hits[canonical_home] = {
                "weight": weighted,
                "support": support,
            }

    return [
        {
            "home": home,
            "weight": round(payload["weight"], 2),
            "support_files": int(payload["support"]),
            "source": "existing_taxonomy",
        }
        for home, payload in sorted(hits.items(), key=lambda item: item[1]["weight"], reverse=True)
    ]


def score_record(
    record_sources: dict[str, str],
    kind: str,
    existing_taxonomy_hints: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], float, str | None, bool]:
    project_hint_weight = max(
        (float(hint.get("weight", 0.0)) for hint in existing_taxonomy_hints or []),
        default=0.0,
    )
    active_source_weights = {
        key: value * WEAK_CONTEXT_SOURCE_SCALE.get(key, 1.0)
        for key, value in SOURCE_WEIGHTS.items()
    } if project_hint_weight < TAXONOMY_HINT_PROJECT_CONTEXT_THRESHOLD else dict(SOURCE_WEIGHTS)

    candidate_scores: dict[str, dict[str, Any]] = defaultdict(lambda: {"score": 0.0, "evidence": []})

    if existing_taxonomy_hints:
        for hint in existing_taxonomy_hints:
            home = hint["home"]
            candidate_scores[home]["score"] += float(hint["weight"])
            candidate_scores[home]["evidence"].append(f"taxonomy:{home}")

    for rule in RULES:
        score = 0.0
        evidence: list[str] = []
        for source_name, source_text in record_sources.items():
            source_weight = active_source_weights.get(source_name, 1.0)
            for pattern, pattern_weight in rule.patterns:
                if pattern_in_text(pattern, source_text):
                    contribution = source_weight * pattern_weight
                    score += contribution
                    evidence.append(f"{source_name}:{pattern}")
        if kind in rule.kind_bonus:
            contribution = rule.kind_bonus[kind]
            score += contribution
            evidence.append(f"kind:{kind}")
        if score > 0:
            candidate_scores[rule.home]["score"] += score
            candidate_scores[rule.home]["evidence"].extend(evidence)

    ranked = sorted(
        (
            {
                "home": home,
                "score": round(payload["score"], 2),
                "evidence": sorted(set(payload["evidence"])),
            }
            for home, payload in candidate_scores.items()
        ),
        key=lambda item: item["score"],
        reverse=True,
    )

    if not ranked:
        return [], 0.0, None, True

    top = ranked[0]
    second = ranked[1]["score"] if len(ranked) > 1 else 0.0
    confidence = top["score"] / (top["score"] + second + AUTOPILOT_REFINE_CONFIDENCE_GAP)
    confidence = round(min(confidence, 0.99), 2)

    min_top_threshold = WEAK_CONTEXT_REVIEW_TOP_MIN if project_hint_weight < TAXONOMY_HINT_PROJECT_CONTEXT_THRESHOLD else 4.0
    needs_refinement = top["score"] < min_top_threshold or confidence < AUTOPILOT_REFINE_CONFIDENCE_THRESHOLD
    suggested_home = None if needs_refinement else top["home"]
    return ranked[:5], confidence, suggested_home, needs_refinement


def resolve_final_home(
    kind: str,
    suggested_home: str | None,
    top_candidates: list[dict[str, Any]],
    autopilot: bool,
) -> tuple[str | None, str]:
    if not autopilot:
        return suggested_home, "refinement_required" if suggested_home is None else "scored"

    if suggested_home:
        return suggested_home, "autopilot_high_confidence"
    return None, "autopilot_blocked"


def sensitivity_flags(record_sources: dict[str, str], metadata: dict[str, Any]) -> list[str]:
    text = " ".join(record_sources.values())
    flags: list[str] = []
    lower = text.lower()
    if contains_any(lower, SENSITIVE_PATTERNS):
        flags.append("sensitive")
    if any(hit in lower for hit in ("client_secret", "oauth", "token_uri", "auth_uri")):
        flags.append("credential")
    if "proxy" in lower or "webshare" in lower:
        flags.append("proxy-list")
    if "passport" in lower or "driver license" in lower or "medicare" in lower:
        flags.append("identity")
    if "tax" in lower or "portfolio" in lower or "statement" in lower:
        flags.append("finance")
    return sorted(set(flags))


def tokenize_for_summary(text: str) -> list[str]:
    tokens = []
    for token in TOKEN_RE.findall(text):
        lower = token.lower().strip("._+-")
        if len(lower) < 3:
            continue
        if lower in PROJECT_STOP_TOKENS:
            continue
        if lower in GENERIC_TAXONOMY_SEGMENTS:
            continue
        if lower in PROJECT_INTERNAL_SEGMENTS:
            continue
        if lower.isdigit():
            continue
        tokens.append(lower)
    return tokens


def summarize_terms(file_tokens: dict[str, set[str]], top_n: int = 20) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    samples: dict[str, list[str]] = defaultdict(list)
    for path, tokens in file_tokens.items():
        for token in tokens:
            counts[token] += 1
            if len(samples[token]) < 3:
                samples[token].append(path)

    items = []
    for token, count in counts.most_common():
        if count < 2:
            continue
        if token in PROJECT_STOP_TOKENS:
            continue
        if len(token) < 4:
            continue
        items.append({"term": token, "count": count, "samples": samples[token]})
        if len(items) >= top_n:
            break
    return items


def confidence_band(confidence: float, needs_refinement: bool) -> str:
    if needs_refinement or confidence < 0.55:
        return "Low"
    if confidence >= 0.8:
        return "High"
    return "Medium"


def summarize_taxonomy_seeds(
    taxonomy_hints: dict[str, tuple[str, float, int]], top_n: int = 40
) -> list[dict[str, Any]]:
    items = []
    for key, (canonical, score, support) in taxonomy_hints.items():
        if not canonical:
            continue
        items.append({"home": canonical, "score": score, "support_files": support, "seed_key": key})
    items.sort(key=lambda item: item["score"], reverse=True)
    return items[:top_n]


def build_manifest_entry(record: FileRecord) -> dict[str, Any]:
    top_candidate = record.top_candidates[0] if record.top_candidates else None
    rationale = "No strong semantic signal; requires arbitration"
    evidence = []
    alternatives = []
    status = record.placement_mode
    destination = record.final_home
    if top_candidate:
        rationale = f"Top signal: {top_candidate['home']} ({top_candidate['score']})"
        evidence = top_candidate["evidence"][:6]
        alternatives = [
            {
                "home": candidate["home"],
                "score": candidate["score"],
                "evidence": candidate["evidence"][:4],
                "rejected_reason": "lower score",
            }
            for candidate in record.top_candidates[1:4]
        ]
    if record.suggested_home is None:
        if record.placement_mode.startswith("autopilot"):
            rationale = (
                "Blocked pending refinement; the manifest keeps evidence and candidate homes, but "
                "does not assign a routable destination"
            )
        else:
            rationale = (
                "No strong semantic signal; requires automated refinement for high-confidence placement"
            )

    return {
        "source_path": record.path,
        "proposed_destination": destination,
        "placement_mode": status,
        "routable": bool(record.final_home and not record.needs_refinement),
        "confidence_score": record.confidence,
        "confidence_band": confidence_band(record.confidence, record.needs_refinement),
        "needs_refinement": bool(record.needs_refinement),
        "rationale": rationale,
        "attribution": {
            "taxonomy_hints": record.taxonomy_hints,
            "primary_signal": top_candidate["home"] if top_candidate else None,
        },
        "evidence": evidence,
        "alternatives": alternatives,
        "flags": record.flags,
        "kind": record.kind,
        "mime": record.mime,
    }


def build_file_evidence(path: Path, root: Path, vision: bool = False) -> FileEvidence:
    mime = mime_type(path)
    kind = detect_kind(path, mime)
    stat_result = path.stat()
    sources, metadata, notes = extract_sources(path, root, kind, mime, vision_enabled=vision)
    combined_for_tokens = " ".join(
        text for source_name, text in sources.items() if source_name != "file"
    )
    if metadata:
        metadata_summary = " ".join(flatten_text_values(metadata, limit=5000))
        if metadata_summary:
            combined_for_tokens += " " + metadata_summary
    tokens = sorted(set(tokenize_for_summary(combined_for_tokens)))

    return FileEvidence(
        path=str(path),
        kind=kind,
        mime=mime,
        size=stat_result.st_size,
        mtime=f"{stat_result.st_mtime:.0f}",
        sources={k: v[:4000] for k, v in sources.items()},
        metadata=metadata,
        notes=notes,
        tokens=tokens,
    )


def record_from_evidence(
    evidence: FileEvidence,
    root: Path,
    taxonomy_hints: dict[str, tuple[str, float, int]],
    autopilot: bool = False,
) -> FileRecord:
    evidence_path = Path(evidence.path)
    file_taxonomy_hints = infer_taxonomy_hints(evidence_path, root, taxonomy_hints)
    top_candidates, confidence, suggested_home, needs_refinement = score_record(
        evidence.sources, evidence.kind, existing_taxonomy_hints=file_taxonomy_hints
    )
    final_home, placement_mode = resolve_final_home(
        evidence.kind, suggested_home, top_candidates, autopilot=autopilot
    )
    flags = sensitivity_flags(evidence.sources, evidence.metadata)

    return FileRecord(
        path=evidence.path,
        kind=evidence.kind,
        mime=evidence.mime,
        size=evidence.size,
        mtime=evidence.mtime,
        sources=evidence.sources,
        metadata=evidence.metadata,
        top_candidates=top_candidates,
        suggested_home=suggested_home,
        taxonomy_hints=file_taxonomy_hints,
        final_home=final_home,
        placement_mode=placement_mode,
        confidence=confidence,
        needs_refinement=needs_refinement,
        flags=sorted(set(flags + evidence.notes)),
        tokens=evidence.tokens,
    )


def scan_file(
    path: Path,
    root: Path,
    taxonomy_hints: dict[str, tuple[str, float, int]],
    autopilot: bool = False,
    vision: bool = False,
    evidence_cache: dict[tuple[str, bool], FileEvidence] | None = None,
) -> tuple[FileRecord, set[str]]:
    cache_key = (str(path), vision)
    evidence = evidence_cache.get(cache_key) if evidence_cache is not None else None
    if evidence is None:
        evidence = build_file_evidence(path, root, vision=vision)
        if evidence_cache is not None:
            evidence_cache[cache_key] = evidence
    record = record_from_evidence(evidence, root, taxonomy_hints, autopilot=autopilot)
    return record, set(evidence.tokens)


def walk_files(root: Path, include_ignored: bool = False) -> Iterable[Path]:
    if root.is_file():
        yield root
        return

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        if not include_ignored:
            dirnames[:] = [
                d
                for d in dirnames
                if d not in DEFAULT_IGNORES and not d.startswith(".")
            ]
        for filename in filenames:
            if filename in {".DS_Store", ".localized", "Thumbs.db", "desktop.ini"}:
                continue
            if filename.startswith("."):
                continue
            if filename.startswith("._"):
                continue
            yield current / filename


def pretty_print(records: list[FileRecord], root: Path, term_summary: list[dict[str, Any]]) -> None:
    home_counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    low_confidence_count = 0
    for rec in records:
        kind_counts[rec.kind] += 1
        destination = rec.final_home or rec.suggested_home
        if rec.needs_refinement:
            home_counts["Needs refinement"] += 1
            low_confidence_count += 1
        elif destination:
            home_counts[destination] += 1
        else:
            home_counts["Unresolved/Unmapped"] += 1

    print(f"Root: {root}")
    print(f"Files scanned: {len(records)}")
    print(f"Low-confidence files: {low_confidence_count}")
    print()

    print("Top candidate homes:")
    for home, count in home_counts.most_common(15):
        print(f"  {count:3d}  {home}")
    print()

    print("Kinds:")
    for kind, count in kind_counts.most_common():
        print(f"  {count:3d}  {kind}")
    print()

    if term_summary:
        print("Repeated terms:")
        for item in term_summary:
            samples = ", ".join(item["samples"])
            print(f"  {item['count']:3d}  {item['term']}  [{samples}]")
        print()

    print("Files:")
    for rec in records:
        home = rec.final_home or rec.suggested_home or "Needs refinement"
        flag_text = f" | flags: {', '.join(rec.flags)}" if rec.flags else ""
        candidate_text = ""
        if rec.top_candidates:
            top = rec.top_candidates[0]
            candidate_text = f" | top: {top['home']} ({top['score']})"
        print(
            f"- {home} ({rec.confidence:.2f}) | {rec.kind:10s} | {rec.path}{candidate_text}{flag_text}"
        )
        if rec.needs_refinement and rec.top_candidates:
            for candidate in rec.top_candidates[:3]:
                evidence = ", ".join(candidate["evidence"][:4])
                print(f"    - {candidate['home']}: {candidate['score']} [{evidence}]")
    print()

    if term_summary:
        print("Likely project/product terms:")
        for item in term_summary:
            samples = ", ".join(item["samples"])
            print(f"- {item['term']} ({item['count']} files) -> {samples}")


def json_output(
    records: list[FileRecord],
    root: Path,
    term_summary: list[dict[str, Any]],
    taxonomy_hints: dict[str, tuple[str, float, int]],
) -> None:
    home_counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    low_confidence_count = 0
    for rec in records:
        kind_counts[rec.kind] += 1
        destination = rec.final_home or rec.suggested_home
        if rec.needs_refinement:
            home_counts["Needs refinement"] += 1
            low_confidence_count += 1
        elif destination:
            home_counts[destination] += 1
        else:
            home_counts["Unresolved/Unmapped"] += 1

    payload = {
        "root": str(root),
        "file_count": len(records),
        "low_confidence_count": low_confidence_count,
        "needs_refinement": low_confidence_count > 0,
        "home_counts": dict(home_counts),
        "kind_counts": dict(kind_counts),
        "project_terms": term_summary,
        "taxonomy_hints": summarize_taxonomy_seeds(taxonomy_hints),
        "files": [
            {
                "path": rec.path,
                "kind": rec.kind,
                "mime": rec.mime,
                "size": rec.size,
                "mtime": rec.mtime,
                "sources": rec.sources,
                "metadata": rec.metadata,
                "top_candidates": rec.top_candidates,
                "suggested_home": rec.suggested_home,
                "taxonomy_hints": rec.taxonomy_hints,
                "final_home": rec.final_home,
                "placement_mode": rec.placement_mode,
                "confidence": rec.confidence,
                "needs_refinement": rec.needs_refinement,
                "flags": rec.flags,
                "tokens": rec.tokens,
            }
            for rec in records
        ],
    }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def manifest_output(
    records: list[FileRecord],
    root: Path,
    term_summary: list[dict[str, Any]],
    taxonomy_hints: dict[str, tuple[str, float, int]],
    autopilot: bool = False,
    refinement_iterations: list[dict[str, Any]] | None = None,
) -> None:
    low_confidence = [
        {
            "source_path": rec.path,
            "proposed_destination": None,
            "placement_mode": rec.placement_mode,
            "reason": "Execution blocked until refinement resolves confidence"
            if autopilot
            else "Needs confidence refinement",
            "candidate_destinations": [candidate["home"] for candidate in rec.top_candidates[:3]],
            "confidence_score": rec.confidence,
        }
        for rec in records
        if rec.needs_refinement
    ]

    if refinement_iterations is None:
        refinement_iterations = [
            {
                "pass": 1,
                "source": "existing_taxonomy_seed",
                "low_confidence_count": len(low_confidence),
            }
        ]

    payload = {
        "root": str(root),
        "file_count": len(records),
        "low_confidence_count": len(low_confidence),
        "needs_refinement": len(low_confidence) > 0,
        "execution_blocked": len(low_confidence) > 0,
        "execution_mode": "autopilot" if autopilot else "review_mode",
        "manifest_iterations": refinement_iterations,
        "project_terms": term_summary,
        "taxonomy_hints": summarize_taxonomy_seeds(taxonomy_hints),
        "entries": [build_manifest_entry(rec) for rec in records],
        "low_confidence": low_confidence,
        "next_actions": {
            "requires_refinement_pass": len(low_confidence) > 0,
            "description": "Re-run semantic scan to tighten low-confidence assignments until low_confidence_count reaches 0 or stabilizes",
            "execution_ready": len(low_confidence) == 0,
        },
    }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def scan_records_with_hints(
    paths: list[Path],
    root: Path,
    taxonomy_hints: dict[str, tuple[str, float, int]],
    autopilot: bool,
    vision: bool,
    evidence_cache: dict[tuple[str, bool], FileEvidence] | None = None,
) -> tuple[list[FileRecord], list[dict[str, Any]], dict[str, set[str]]]:
    records: list[FileRecord] = []
    file_tokens: dict[str, set[str]] = {}

    for path in paths:
        if not path.is_file():
            continue
        try:
            record, tokens = scan_file(
                path,
                root=root,
                taxonomy_hints=taxonomy_hints,
                autopilot=autopilot,
                vision=vision,
                evidence_cache=evidence_cache,
            )
        except Exception as exc:  # defensive: scanner should not die on one bad file
            evidence = FileEvidence(
                path=str(path),
                kind="unreadable",
                mime="application/octet-stream",
                size=0,
                mtime="0",
                sources={"path": str(path).lower(), "name": path.name.lower()},
                metadata={},
                notes=[f"scan_error:{exc.__class__.__name__}"],
                tokens=[],
            )
            if evidence_cache is not None:
                evidence_cache[(str(path), vision)] = evidence
            record = record_from_evidence(evidence, root, taxonomy_hints, autopilot=autopilot)
            tokens = set(evidence.tokens)
        records.append(record)
        file_tokens[str(path)] = tokens

    records.sort(key=lambda item: item.path)
    term_summary = summarize_terms(file_tokens)
    return records, term_summary, file_tokens


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract semantic evidence from a folder for tidy-folder.")
    parser.add_argument("root", nargs="?", default=".", help="Folder or file to scan")
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of a human-readable report",
    )
    output_group.add_argument(
        "--manifest",
        action="store_true",
        help="Emit a placement manifest for execution",
    )
    parser.add_argument(
        "--autopilot",
        action="store_true",
        help="In manifest/json mode, assign every item a deterministic destination path and expose low-confidence entries for refinement",
    )
    parser.add_argument(
        "--include-ignored",
        action="store_true",
        help="Include ignored build/system folders such as .git and node_modules",
    )
    parser.add_argument(
        "--vision",
        action="store_true",
        help="Enable optional image/video vision captioning for visual-semantic scoring",
    )
    parser.add_argument(
        "--vision-provider",
        default="hf",
        choices=("hf", "openai"),
        help="Vision backend to use when --vision is enabled: hf (local BLIP captioning) or openai (API-based multimodal model).",
    )
    parser.add_argument(
        "--vision-model",
        default="",
        help="Optional provider model name (default: gpt-4o-mini for openai, inferred default for hf).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(args.root).expanduser().resolve()
    if not root.exists():
        print(f"error: path does not exist: {root}", file=sys.stderr)
        return 2

    paths = list(walk_files(root, include_ignored=args.include_ignored))

    if args.vision:
        set_vision_provider(args.vision_provider, args.vision_model)
        if args.vision_provider != "openai":
            ensure_local_vision_runtime(sys.argv)
        vision_ready, vision_status = validate_vision_readiness(paths)
        if not vision_ready:
            print(
                "error: --vision was requested but semantic vision analysis is not available.",
                file=sys.stderr,
            )
            print(f"Vision check: {json.dumps(vision_status, ensure_ascii=False)}", file=sys.stderr)
            return 2

    base_taxonomy_hints = collect_existing_taxonomy_hints(paths, root)
    taxonomy_hints = dict(base_taxonomy_hints)
    evidence_cache: dict[tuple[str, bool], FileEvidence] = {}

    records, term_summary, _ = scan_records_with_hints(
        paths,
        root=root,
        taxonomy_hints=taxonomy_hints,
        autopilot=args.autopilot,
        vision=args.vision,
        evidence_cache=evidence_cache,
    )

    refinement_iterations = [
        {
            "pass": 1,
            "source": "existing_taxonomy_seed",
            "low_confidence_count": sum(1 for record in records if record.needs_refinement),
            "taxonomy_hints": len(taxonomy_hints),
        }
    ]

    if args.autopilot:
        previous_low_confidence = refinement_iterations[0]["low_confidence_count"]
        previous_hints = dict(taxonomy_hints)
        for refinement_pass in range(2, AUTOPILOT_REFINEMENT_PASSES + 1):
            if previous_low_confidence == 0:
                break

            inferred_hints = collect_refinement_hints(
                records,
                root,
                min_confidence=AUTOPILOT_REFINEMENT_MIN_CONFIDENCE,
                min_support=AUTOPILOT_REFINEMENT_MIN_SUPPORT,
                min_ratio=AUTOPILOT_REFINEMENT_MIN_RATIO,
            )
            if not inferred_hints:
                break

            merged_hints = merge_taxonomy_hints(previous_hints, inferred_hints)
            if merged_hints == previous_hints:
                break

            next_records, next_term_summary, _ = scan_records_with_hints(
                paths,
                root=root,
                taxonomy_hints=merged_hints,
                autopilot=args.autopilot,
                vision=args.vision,
                evidence_cache=evidence_cache,
            )
            next_low_confidence = sum(1 for record in next_records if record.needs_refinement)
            refinement_iterations.append(
                {
                    "pass": refinement_pass,
                    "source": "autopilot_refinement_seed",
                    "low_confidence_count": next_low_confidence,
                    "taxonomy_hints": len(merged_hints),
                    "added_hints": len(inferred_hints),
                    "improvement": previous_low_confidence - next_low_confidence,
                }
            )

            if next_low_confidence >= previous_low_confidence:
                break

            records = next_records
            term_summary = next_term_summary
            taxonomy_hints = merged_hints
            previous_hints = merged_hints
            previous_low_confidence = next_low_confidence
            if previous_low_confidence == 0:
                break

    if args.json:
        json_output(records, root, term_summary, taxonomy_hints)
    elif args.manifest:
        manifest_output(
            records,
            root,
            term_summary,
            taxonomy_hints,
            autopilot=args.autopilot,
            refinement_iterations=refinement_iterations,
        )
    else:
        pretty_print(records, root, term_summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
