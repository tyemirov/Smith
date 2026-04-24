#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Deterministic helper for the Git Release skill."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


SEMVER_TAG_RE = re.compile(r"^v?(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?$")
CALVER_TAG_RE = re.compile(
    r"^v?(?P<year>\d{4})\.(?P<month>\d{1,2})\.(?P<day>\d{1,2})"
    r"(?:\.(?P<hour>\d{1,2})(?:\.(?P<minute>\d{1,2})(?:\.(?P<second>\d{1,2}))?)?)?$"
)
RELEASE_HEADING_RE = re.compile(
    r"^##\s+\[?(?:v?(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?|v?\d{4}\.\d{1,2}\.\d{1,2}(?:\.\d{1,2}(?:\.\d{1,2}(?:\.\d{1,2})?)?)?)\]?(?:[^\n]*)?$",
    re.MULTILINE,
)


class HelperError(Exception):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


def run(command: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and proc.returncode != 0:
        raise HelperError(
            f"command failed: {' '.join(command)}",
            {
                "command": command,
                "returncode": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
            },
        )
    return proc


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def fail(message: str, details: dict[str, Any] | None = None) -> None:
    emit({"ok": False, "error": message, "details": details or {}})
    raise SystemExit(1)


def require_tools(names: list[str]) -> list[str]:
    return [name for name in names if shutil.which(name) is None]


def repo_root() -> Path:
    return Path(run(["git", "rev-parse", "--show-toplevel"]).stdout.strip())


def gh_json(command: list[str], cwd: Path) -> Any:
    return json.loads(run(command, cwd=cwd).stdout or "null")


def resolve_default_branch(cwd: Path, override: str | None = None) -> str:
    if override:
        return override

    gh_proc = run(["gh", "repo", "view", "--json", "defaultBranchRef"], cwd=cwd, check=False)
    if gh_proc.returncode == 0:
        data = json.loads(gh_proc.stdout)
        name = (data.get("defaultBranchRef") or {}).get("name")
        if name:
            return name

    remote_proc = run(["git", "remote", "show", "origin"], cwd=cwd)
    for line in remote_proc.stdout.splitlines():
        if "HEAD branch:" in line:
            return line.rsplit(":", 1)[1].strip()

    raise HelperError("could not resolve default branch")


def all_tags(cwd: Path) -> list[str]:
    return run(["git", "tag", "--sort=-version:refname"], cwd=cwd).stdout.splitlines()


def calver_match(tag: str) -> re.Match[str] | None:
    match = CALVER_TAG_RE.match(tag)
    if not match:
        return None
    try:
        dt.date(int(match.group("year")), int(match.group("month")), int(match.group("day")))
    except ValueError:
        return None
    for name, upper in (("hour", 23), ("minute", 59), ("second", 59)):
        value = match.group(name)
        if value is not None and not 0 <= int(value) <= upper:
            return None
    return match


def tag_scheme(tag: str) -> str | None:
    if calver_match(tag):
        return "calver"
    if SEMVER_TAG_RE.match(tag):
        return "semver"
    return None


def parse_release_timestamp(value: str | None, release_date: str | None = None) -> dt.datetime:
    if not value:
        if release_date:
            return dt.datetime.combine(parse_release_date(release_date), dt.time())
        return dt.datetime.now().astimezone()
    try:
        normalized = value.replace("Z", "+00:00")
        return dt.datetime.fromisoformat(normalized)
    except ValueError as exc:
        try:
            return dt.datetime.combine(dt.date.fromisoformat(value), dt.time())
        except ValueError:
            raise HelperError(
                "release timestamp must use ISO format such as YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD",
                {"release_timestamp": value},
            ) from exc


def parse_release_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise HelperError("release date must use YYYY-MM-DD format", {"release_date": value}) from exc


def calver_sort_key(tag: str) -> tuple[int, int, int, int, int, int]:
    match = calver_match(tag)
    if not match:
        raise ValueError(f"not a CalVer tag: {tag}")
    return (
        int(match.group("year")),
        int(match.group("month")),
        int(match.group("day")),
        int(match.group("hour")) if match.group("hour") is not None else -1,
        int(match.group("minute")) if match.group("minute") is not None else -1,
        int(match.group("second")) if match.group("second") is not None else -1,
    )


def calver_from_timestamp(timestamp: dt.datetime, precision: str) -> str:
    parts = [timestamp.year, timestamp.month, timestamp.day]
    if precision in {"hour", "minute", "second"}:
        parts.append(timestamp.hour)
    if precision in {"minute", "second"}:
        parts.append(timestamp.minute)
    if precision == "second":
        parts.append(timestamp.second)
    return ".".join(str(part) for part in parts)


def calver_candidate(tags: list[str], release_timestamp: dt.datetime) -> dict[str, Any]:
    existing = set(tags)
    all_candidates = [
        ("hour", calver_from_timestamp(release_timestamp, "hour")),
        ("minute", calver_from_timestamp(release_timestamp, "minute")),
        ("second", calver_from_timestamp(release_timestamp, "second")),
    ]
    minimum_precision = "second" if release_timestamp.second else "minute" if release_timestamp.minute else "hour"
    minimum_index = next(index for index, (precision, _) in enumerate(all_candidates) if precision == minimum_precision)
    candidates = all_candidates[minimum_index:]
    chosen_precision, chosen = candidates[-1]
    collision_chain: list[str] = []
    for precision, candidate in candidates:
        if candidate in existing or f"v{candidate}" in existing:
            collision_chain.append(candidate)
            continue
        chosen_precision, chosen = precision, candidate
        break

    calver_tags = [tag for tag in tags if tag_scheme(tag) == "calver"]
    latest_calver = sorted(calver_tags, key=calver_sort_key, reverse=True)[0] if calver_tags else None
    candidate_key = calver_sort_key(chosen)
    latest_key = calver_sort_key(latest_calver) if latest_calver else None
    errors: list[str] = []
    if chosen in existing or f"v{chosen}" in existing:
        errors.append("CalVer timestamp candidate already exists at second precision")
    if latest_key and candidate_key <= latest_key:
        errors.append("CalVer timestamp is not later than the latest CalVer tag")

    return {
        "ok": not errors,
        "candidate": chosen,
        "precision": chosen_precision,
        "release_timestamp": release_timestamp.isoformat(),
        "latest_calver_tag": latest_calver,
        "collision_chain": collision_chain,
        "errors": errors,
    }


def version_info(cwd: Path, release_timestamp: dt.datetime) -> dict[str, Any]:
    tags = all_tags(cwd)
    semver_tags = [tag for tag in tags if tag_scheme(tag) == "semver"]
    calver_tags = sorted((tag for tag in tags if tag_scheme(tag) == "calver"), key=calver_sort_key, reverse=True)
    version_tags = [tag for tag in tags if tag_scheme(tag)]
    calver = calver_candidate(tags, release_timestamp)

    if semver_tags and calver_tags:
        scheme_guess = "mixed"
    elif calver_tags:
        scheme_guess = "calver"
    elif semver_tags:
        scheme_guess = "semver"
    else:
        scheme_guess = "none"

    latest_by_guess = None
    if scheme_guess == "calver":
        latest_by_guess = calver_tags[0]
    elif scheme_guess == "semver":
        latest_by_guess = semver_tags[0]
    elif version_tags:
        latest_by_guess = version_tags[0]

    return {
        "scheme_guess": scheme_guess,
        "latest_tag": latest_by_guess,
        "latest_any_version_tag": version_tags[0] if version_tags else None,
        "latest_semver_tag": semver_tags[0] if semver_tags else None,
        "latest_calver_tag": calver_tags[0] if calver_tags else None,
        "version_tags": version_tags[:20],
        "next_calver": calver["candidate"],
        "calver_candidate": calver,
        "release_date": release_timestamp.date().isoformat(),
        "release_timestamp": release_timestamp.isoformat(),
        "calver_format": "YYYY.M.D.H[.m[.s]]",
    }


def detect_validation_candidates(cwd: Path) -> list[str]:
    candidates: list[str] = []

    makefile = cwd / "Makefile"
    if makefile.exists() and re.search(r"^ci\s*:", makefile.read_text(encoding="utf-8", errors="replace"), re.MULTILINE):
        candidates.append("make ci")

    package_json = cwd / "package.json"
    if package_json.exists():
        try:
            scripts = json.loads(package_json.read_text(encoding="utf-8")).get("scripts", {})
        except json.JSONDecodeError:
            scripts = {}
        runner = "npm"
        if (cwd / "pnpm-lock.yaml").exists():
            runner = "pnpm"
        elif (cwd / "yarn.lock").exists():
            runner = "yarn"
        for script_name in ("ci", "test"):
            if script_name in scripts:
                candidates.append(f"{runner} run {script_name}")

    if (cwd / "pyproject.toml").exists() or (cwd / "pytest.ini").exists():
        if not candidates:
            candidates.append("pytest")

    return candidates


def command_preflight(args: argparse.Namespace) -> int:
    missing = require_tools(["git", "gh", "gix"])
    if missing:
        fail("required tools are missing", {"missing_tools": missing})

    cwd = repo_root()
    default_branch = resolve_default_branch(cwd, args.default_branch)
    versions = version_info(cwd, parse_release_timestamp(args.release_timestamp, args.release_date))
    status_lines = run(["git", "status", "--short"], cwd=cwd).stdout.splitlines()
    open_prs = gh_json(
        ["gh", "pr", "list", "--base", default_branch, "--state", "open", "--json", "number,title,headRefName,url"],
        cwd,
    )
    payload = {
        "ok": not status_lines and not open_prs,
        "repo_root": str(cwd),
        "default_branch": default_branch,
        "current_branch": run(["git", "branch", "--show-current"], cwd=cwd).stdout.strip(),
        "dirty_status": status_lines,
        "open_prs": open_prs,
        "latest_tag": versions["latest_tag"],
        "version_info": versions,
        "validation_candidates": detect_validation_candidates(cwd),
    }
    emit(payload)
    return 0 if payload["ok"] else 1


def normalize_markdown(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines()).strip()


def command_insert_changelog(args: argparse.Namespace) -> int:
    cwd = repo_root()
    notes_path = Path(args.notes_file)
    notes = notes_path.read_text(encoding="utf-8").strip()
    if not notes:
        fail("release notes file is empty", {"notes_file": str(notes_path)})

    changelog = cwd / args.changelog
    if changelog.exists():
        existing = changelog.read_text(encoding="utf-8")
    else:
        existing = "# Changelog\n\n"

    first_heading = next((line.strip() for line in notes.splitlines() if line.startswith("## ")), None)
    if first_heading and re.search(rf"^{re.escape(first_heading)}$", existing, re.MULTILINE):
        if normalize_markdown(notes) in normalize_markdown(existing):
            emit({"ok": True, "changed": False, "changelog": str(changelog), "reason": "release notes already present"})
            return 0
        fail("changelog already contains a matching release heading with different content", {"heading": first_heading})

    section = notes.rstrip() + "\n\n"
    match = RELEASE_HEADING_RE.search(existing)
    if match:
        updated = existing[: match.start()] + section + existing[match.start() :]
    else:
        h1 = re.search(r"^# .*$", existing, re.MULTILINE)
        if h1:
            insert_at = h1.end()
            while insert_at < len(existing) and existing[insert_at] == "\n":
                insert_at += 1
            updated = existing[:insert_at].rstrip() + "\n\n" + section + existing[insert_at:].lstrip()
        else:
            updated = section + existing.lstrip()

    changelog.write_text(updated, encoding="utf-8")
    emit({"ok": True, "changed": updated != existing, "changelog": str(changelog)})
    return 0


def command_publish_release(args: argparse.Namespace) -> int:
    missing = require_tools(["git", "gh"])
    if missing:
        fail("required tools are missing", {"missing_tools": missing})

    cwd = repo_root()
    notes_path = Path(args.notes_file)
    expected_notes = normalize_markdown(notes_path.read_text(encoding="utf-8"))
    if not expected_notes:
        fail("release notes file is empty", {"notes_file": str(notes_path)})

    title = args.title or f"Release {args.version}"
    view_command = [
        "gh",
        "release",
        "view",
        args.version,
        "--json",
        "tagName,name,body,publishedAt,isDraft,isPrerelease,targetCommitish,url",
    ]
    existing_proc = run(view_command, cwd=cwd, check=False)
    action = "none"
    command: list[str] | None = None

    if existing_proc.returncode != 0:
        action = "created"
        command = [
            "gh",
            "release",
            "create",
            args.version,
            "--verify-tag",
            "--title",
            title,
            "--notes-file",
            str(notes_path),
            "--latest",
        ]
    else:
        existing = json.loads(existing_proc.stdout)
        actual_notes = normalize_markdown(existing.get("body") or "")
        needs_edit = (
            existing.get("tagName") != args.version
            or existing.get("name") != title
            or existing.get("isDraft")
            or actual_notes != expected_notes
        )
        if needs_edit:
            action = "updated"
            command = [
                "gh",
                "release",
                "edit",
                args.version,
                "--verify-tag",
                "--title",
                title,
                "--notes-file",
                str(notes_path),
                "--draft=false",
                "--latest",
            ]

    if command:
        run(command, cwd=cwd)

    refreshed = gh_json(view_command, cwd)
    errors: list[str] = []
    if refreshed.get("tagName") != args.version:
        errors.append("GitHub Release object has the wrong tagName")
    if refreshed.get("isDraft"):
        errors.append("GitHub Release object is still a draft")
    if not refreshed.get("publishedAt"):
        errors.append("GitHub Release object has no publishedAt timestamp")
    if normalize_markdown(refreshed.get("body") or "") != expected_notes:
        errors.append("GitHub Release body does not match generated release notes")

    payload = {"ok": not errors, "action": action, "release": refreshed, "errors": errors}
    emit(payload)
    return 0 if not errors else 1


def ls_remote_tag_commit(cwd: Path, version: str) -> str:
    peeled = run(["git", "ls-remote", "--tags", "origin", f"refs/tags/{version}^{{}}"], cwd=cwd).stdout.strip()
    if peeled:
        return peeled.split()[0]
    direct = run(["git", "ls-remote", "--tags", "origin", f"refs/tags/{version}"], cwd=cwd).stdout.strip()
    return direct.split()[0] if direct else ""


def fetch_url(url: str, head_only: bool = False) -> dict[str, Any]:
    method = "HEAD" if head_only else "GET"
    request = urllib.request.Request(url, method=method, headers={"User-Agent": "gitrelease-helper/1"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = "" if head_only else response.read(1_000_000).decode("utf-8", errors="replace")
            return {"ok": True, "status": response.status, "url": response.geturl(), "body": body}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "error": str(exc), "url": url}
    except urllib.error.URLError as exc:
        return {"ok": False, "error": str(exc), "url": url}


def optional_gh_json(command: list[str], cwd: Path) -> dict[str, Any]:
    proc = run(command, cwd=cwd, check=False)
    if proc.returncode == 0:
        return {"ok": True, "data": json.loads(proc.stdout or "null")}
    return {"ok": False, "returncode": proc.returncode, "stderr": proc.stderr.strip(), "stdout": proc.stdout.strip()}


def collect_pages(cwd: Path, expected_texts: list[str]) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    pages = optional_gh_json(["gh", "api", "repos/{owner}/{repo}/pages"], cwd)
    if not pages["ok"]:
        stderr = pages.get("stderr", "")
        if "404" in stderr or "Not Found" in stderr:
            return {"configured": False, "lookup": pages}, []
        errors.append("GitHub Pages configuration lookup failed")
        return {"configured": None, "lookup": pages}, errors

    data = pages["data"] or {}
    html_url = data.get("html_url")
    result: dict[str, Any] = {
        "configured": True,
        "config": data,
        "latest_build": optional_gh_json(
            ["gh", "api", "repos/{owner}/{repo}/pages/builds/latest", "--jq", "{status,error,commit,created_at,updated_at,url}"],
            cwd,
        ),
        "latest_deployment": optional_gh_json(
            [
                "gh",
                "api",
                "repos/{owner}/{repo}/deployments?environment=github-pages",
                "--jq",
                ".[0] | {id,sha,ref,created_at,statuses_url}",
            ],
            cwd,
        ),
    }
    if not html_url:
        errors.append("GitHub Pages is configured but has no html_url")
        return result, errors

    head = fetch_url(html_url, head_only=True)
    if not head["ok"]:
        head = fetch_url(html_url, head_only=False)
    result["site_probe"] = {key: value for key, value in head.items() if key != "body"}
    if not head["ok"]:
        errors.append("GitHub Pages URL is not reachable")

    if expected_texts:
        page = fetch_url(html_url, head_only=False)
        body = page.get("body", "") if page["ok"] else ""
        missing = [text for text in expected_texts if text not in body]
        result["expected_text_check"] = {"ok": not missing, "missing": missing}
        if missing:
            errors.append("GitHub Pages URL does not contain expected release text")

    return result, errors


def collect_runs(cwd: Path, default_branch: str, release_commit: str) -> dict[str, Any]:
    return {
        "for_release_commit": optional_gh_json(
            [
                "gh",
                "run",
                "list",
                "--commit",
                release_commit,
                "--json",
                "databaseId,name,event,status,conclusion,headSha,url",
                "--limit",
                "20",
            ],
            cwd,
        ),
        "release_events": optional_gh_json(
            [
                "gh",
                "run",
                "list",
                "--event",
                "release",
                "--json",
                "databaseId,name,event,status,conclusion,headSha,url",
                "--limit",
                "20",
            ],
            cwd,
        ),
        "default_branch_push_events": optional_gh_json(
            [
                "gh",
                "run",
                "list",
                "--event",
                "push",
                "--branch",
                default_branch,
                "--json",
                "databaseId,name,event,status,conclusion,headSha,url",
                "--limit",
                "20",
            ],
            cwd,
        ),
    }


def command_verify_release(args: argparse.Namespace) -> int:
    missing = require_tools(["git", "gh"])
    if missing:
        fail("required tools are missing", {"missing_tools": missing})

    cwd = repo_root()
    default_branch = resolve_default_branch(cwd, args.default_branch)
    release_commit = run(["git", "rev-parse", args.release_commit], cwd=cwd).stdout.strip()
    errors: list[str] = []

    local_tag_proc = run(["git", "rev-list", "-n", "1", args.version], cwd=cwd, check=False)
    local_tag_commit = local_tag_proc.stdout.strip() if local_tag_proc.returncode == 0 else ""
    remote_tag_commit = ls_remote_tag_commit(cwd, args.version)
    if local_tag_commit != release_commit:
        errors.append("local tag does not point at release commit")
    if remote_tag_commit != release_commit:
        errors.append("remote tag does not point at release commit")

    release_proc = run(
        [
            "gh",
            "release",
            "view",
            args.version,
            "--json",
            "tagName,name,body,publishedAt,isDraft,isPrerelease,targetCommitish,url",
        ],
        cwd=cwd,
        check=False,
    )
    release: dict[str, Any] | None = None
    if release_proc.returncode != 0:
        errors.append("GitHub Release object is missing or unreadable")
    else:
        release = json.loads(release_proc.stdout)
        if release.get("tagName") != args.version:
            errors.append("GitHub Release object has the wrong tagName")
        if release.get("isDraft"):
            errors.append("GitHub Release object is still a draft")
        if not release.get("publishedAt"):
            errors.append("GitHub Release object has no publishedAt timestamp")
        if args.notes_file:
            expected_notes = normalize_markdown(Path(args.notes_file).read_text(encoding="utf-8"))
            actual_notes = normalize_markdown(release.get("body") or "")
            if expected_notes != actual_notes:
                errors.append("GitHub Release body does not match generated release notes")

    watched_runs: list[dict[str, Any]] = []
    for run_id in args.watch_run:
        proc = run(["gh", "run", "watch", str(run_id), "--exit-status"], cwd=cwd, check=False)
        watched_runs.append(
            {
                "run_id": run_id,
                "returncode": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
            }
        )
        if proc.returncode != 0:
            errors.append(f"watched GitHub Actions run failed or did not complete: {run_id}")

    pages, page_errors = ({"skipped": True}, [])
    if not args.skip_pages:
        pages, page_errors = collect_pages(cwd, args.expect_pages_text)
        errors.extend(page_errors)

    payload = {
        "ok": not errors,
        "repo_root": str(cwd),
        "default_branch": default_branch,
        "version": args.version,
        "release_commit": release_commit,
        "local_tag_commit": local_tag_commit,
        "remote_tag_commit": remote_tag_commit,
        "release": release,
        "runs": collect_runs(cwd, default_branch, release_commit),
        "watched_runs": watched_runs,
        "pages": pages,
        "final_status": run(["git", "status", "--short"], cwd=cwd).stdout.splitlines(),
        "errors": errors,
    }
    emit(payload)
    return 0 if not errors else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic helper for the Git Release skill.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight", help="Check deterministic release preconditions.")
    preflight.add_argument("--default-branch")
    preflight.add_argument("--release-date", help="Release date in YYYY-MM-DD format. Used as midnight if no timestamp is provided.")
    preflight.add_argument(
        "--release-timestamp",
        help="Release timestamp in ISO format for CalVer candidate generation, for example 2026-04-23T17:05:12.",
    )
    preflight.set_defaults(func=command_preflight)

    changelog = subparsers.add_parser("insert-changelog", help="Insert generated release notes into CHANGELOG.md.")
    changelog.add_argument("--notes-file", required=True)
    changelog.add_argument("--changelog", default="CHANGELOG.md")
    changelog.set_defaults(func=command_insert_changelog)

    publish = subparsers.add_parser("publish-release", help="Create or update the GitHub Release object.")
    publish.add_argument("--version", required=True)
    publish.add_argument("--notes-file", required=True)
    publish.add_argument("--title")
    publish.set_defaults(func=command_publish_release)

    verify = subparsers.add_parser("verify-release", help="Verify remote tag, GitHub Release, runs, and Pages.")
    verify.add_argument("--version", required=True)
    verify.add_argument("--release-commit", required=True)
    verify.add_argument("--notes-file")
    verify.add_argument("--default-branch")
    verify.add_argument("--watch-run", action="append", default=[])
    verify.add_argument("--skip-pages", action="store_true")
    verify.add_argument("--expect-pages-text", action="append", default=[])
    verify.set_defaults(func=command_verify_release)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except HelperError as exc:
        fail(str(exc), exc.details)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
