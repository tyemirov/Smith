---
name: tidy-folder
description: |
  Reorganize messy folders into a clean, discoverable structure based on the user's life domains and interests -- not by file type. Use this skill whenever the user asks to organize, tidy, clean up, sort, or declutter any folder or directory. Only use it when the target folder is explicitly provided or clearly identified in the request; if no target folder is specified, stop and ask for one. This skill applies to any directory -- Downloads, Documents, project folders, shared drives, photo libraries, or any other folder the user wants organized.
---

# Tidy Folder

You are reorganizing a folder to make its contents **discoverable** -- meaning the user can find any file by thinking about what it *is*, not what format it's in.

## The Core Principle

**Organize by meaning, not by file type.** A child's lab result is not an "academic paper" just because it's a PDF. A lease is not a "document" -- it's a housing record. A product manual is not "reading material" -- it's a home reference. The taxonomy should reflect how the user's brain works: "Where would I look for Alice's report card?" The answer is "Kids", not "PDFs" or "Documents".

This is the single most important thing to internalize. Every decision flows from it.

## The Specificity Ladder

When more than one home seems plausible, choose the most specific one that matches how the user would actually search for the file:

1. Named project, client, product, brand, campaign, or event.
2. Life domain or owner group.
3. Artifact role inside that domain.
4. File type or software export only as a last resort.

A project's support files belong with that project even when they are images, screenshots, videos, audio, or generated art. If the user would look for the file by project name first, it does not belong in `Photos` just because it has pixels. Use `Photos` for memory photos and event snapshots whose primary purpose is the moment itself, not the project.

When helpful, create a role folder inside the specific home, such as `Cover-Art`, `Screenshots`, `Exports`, `References`, `Source`, `Drafts`, `Receipts`, or `Statements`.

## Attribution Sources

When deciding where a file belongs, use every reliable clue available before falling back to a generic bucket:

- Filename and surrounding folder names.
- Existing folder taxonomy (already organized parents/siblings) as a high-confidence prior.
- Visible content in the file itself.
- Embedded metadata, tags, titles, author names, and creation timestamps.
- OCR text from images or slide decks.
- Frame grabs from videos.
- Audio tags, transcripts, or obvious generated-song metadata.

If any clue points to a named project, client, product, brand, campaign, or event, that attribution outranks medium-based buckets like `Photos`, `Videos`, or `Audio`. A file with a generic name but project-specific content should still file with the project.

When existing taxonomy exists, do not treat it as decoration: it must become a scoring input.

### Evidence Precedence

When signals conflict, resolve them in this order:

1. **Structural safety and atomicity first**
   - Preserve coherent project roots and already-semantic subtrees unless direct file-level evidence isolates a misfiled leaf.
   - Never split a detected project root because of file extension, medium, or a weak one-off clue.

2. **Direct file evidence second**
   - Embedded text, visible content, OCR, metadata, tags, titles, and repeated cross-file signals outrank filenames and folder labels.
   - If the contents clearly say what the file is, trust the contents over the name.

3. **Existing taxonomy third**
   - If a file already sits inside a coherent existing home, keep that prior unless direct evidence clearly contradicts it.
   - Existing taxonomy is a strong prior, not an untouchable rule.

4. **User lookup behavior fourth**
   - If multiple homes remain semantically valid, choose the one where the user would look first.
   - This is the tie-breaker for cross-domain files like leases, enrollment forms, and project collateral.

5. **Path and filename priors fifth**
   - Nearby folders, basenames, repeated tokens, and sibling patterns matter when direct evidence is weak or absent.
   - Treat them as supporting context, not primary truth.

6. **Medium and extension last**
   - `Photos`, `Videos`, `Audio`, and extension-like buckets are only valid when no stronger semantic home exists.
   - A medium bucket never outranks project attribution or clear domain evidence.

7. **Helper output last**
   - Helper scores, draft homes, and helper confidence are advisory summaries of evidence.
   - If they conflict with the rules above, agents must override them and record why.

## Decision Authority

This skill is **snapshot-first and role-audited**.

- Helper scripts gather evidence, persist artifacts, and may propose candidate homes.
- Helper scripts do **not** decide final taxonomy on their own.
- The controller always creates a rollback snapshot and run lock before scanning or restoring.
- The skill requires an explicit target folder. Do not infer a folder or pick one on the user's behalf when none was provided.
- Execution safety comes from the current run being free of blockers plus explicit snapshot restoration support, not from separate approval artifacts.
- The role graph still matters:
  - `Scout` gathers evidence.
  - `Router` records placement decisions and rationale.
  - `Gatekeeper` challenges weak placements and blocks ambiguous execution.
  - `Supervisor` owns run state, snapshots, and lock/lease behavior.
  - `Executor` performs only current-run moves that cleared the validation gates.

If helper output conflicts with stronger file-level evidence, existing taxonomy, or cross-file context, the workflow must override the helper output and record why in the handoff artifacts.

## Recommended Tooling

Use the `scripts/semantic_scan.py` helper when it is available. Its job is to gather evidence, not to make final decisions:

- It runs through `uv` and installs its Python dependencies automatically.
- Its Python baseline uses `pypdf`, `Pillow`, `mutagen`, and `openpyxl` to cover the common portable cases: PDF text, image metadata, audio/video tags, and spreadsheet previews.
- File type and MIME detection.
- Text previews from PDFs, documents, spreadsheets, CSV, JSON, and plain text.
- Metadata from images and media files.
- OCR or frame-grab text when local tools are present.
- Candidate homes with evidence and confidence.
- The helper contract is to surface evidence packets and draft candidate homes that agents review. Its outputs are advisory, not authoritative.
- The controller-backed workflow reuses a persistent evidence cache under `./.tidy-folder-snapshots/semantic-evidence-cache.json` so repeated manifest/audit passes do not re-extract every unchanged file.

Use `scripts/run_tidy_folder.py` for the full workflow. It creates the rollback snapshot for the provided folder, persists draft manifests and handoff artifacts, executes immediately when the current run is clear, and can restore any prior execution snapshot by id.

### Dependency and execution model

- This skill must use `uv` for Python execution.
- Do not install deps with `pip`, `pipx`, or global `venv` workflows for this script.
- For helper debugging only, you may inspect evidence directly with:

```bash
cd /Users/tyemirov/Development/agentSkills/tidy-folder
/opt/homebrew/bin/uv run ./scripts/semantic_scan.py /path/to/folder --manifest --autopilot
```

- For actual skill use, always start with the controller so the folder is snapshotted before any scan or move:

```bash
cd /Users/tyemirov/Development/agentSkills/tidy-folder
python3 ./scripts/run_tidy_folder.py /path/to/folder
python3 ./scripts/run_tidy_folder.py /path/to/folder --execute
python3 ./scripts/run_tidy_folder.py /path/to/folder --restore-snapshot <snapshot_id>
```

- Do not run the skill against an unspecified folder. If the user did not name a folder, ask for the folder first.

- The script uses a lightweight `uv` shebang (`#!/usr/bin/env -S uv run --script`) and declares its baseline Python requirements inline, so ordinary non-vision scans do not pay the local vision-model install cost.
- Vision mode is opt-in and explicit (recommended for images/videos):

```bash
uv run ./scripts/semantic_scan.py /path/to/folder --manifest --autopilot --vision
uv run ./scripts/semantic_scan.py /path/to/folder --manifest --autopilot --vision --vision-provider openai
```

- Vision mode stays opt-in. When you request `--vision --vision-provider hf`, the script bootstraps the extra local `transformers`/`torch` runtime on demand through `uv`; use `--vision-provider openai` to route image/video understanding through an API model instead (requires `OPENAI_API_KEY`).
- Vision readiness checks stay lightweight: they validate provider/tool prerequisites without forcing a warm-up caption pass before the main scan.
- Helpers are optional accelerators. If a helper cannot answer a question cleanly, continue with shell inspection and agent reasoning rather than pretending the helper made a decision.

Native tools like `ffmpeg`, `pdftotext`, `tesseract`, `mdls`, `file`, `strings`, and `antiword` are optional accelerators. If a machine does not have them, the scanner still works, but some files will stay low-confidence until enough evidence is available.

Treat the script as an evidence collector and artifact writer. The skill's AI agents produce the inferred taxonomy without user intervention.
- `needs_review` is not part of the human workflow contract. Helper-reported `low_confidence` is an escalation signal for `Router` and `Gatekeeper`, not independent authority.
- Helper-generated `proposed_destination` values are drafts. Agents may keep, refine, or reject them.
- Low-confidence draft entries are non-routable by default: keep their evidence and candidates explicit until reconciliation resolves them.
- Narrow deterministic fallback homes are allowed only after evidence extraction is exhausted and the workflow still records them as blocked candidates: `Screen-Captures` for unattributed screenshots/screencasts, plus `Recovery/Unknown-Text` and `Recovery/Unknown-Binary` for genuinely opaque leftovers.

## The Banned Words List

**NEVER use any of the following as a category name.** These are vague abstractions that tell the user nothing about what's inside:

- **Documents** -- everything is a document. This says nothing.
- **Files** -- even more meaningless than "Documents".
- **Data** -- what data? Tax data? Health data? Kids' school data? Name the domain.
- **Stuff** / **Things** / **Items** -- not categories, just avoidance of thought.
- **Personal** -- as opposed to what? Everything in the folder is personal. Be specific: is it Health? Finance? Family?
- **Misc** / **Miscellaneous** / **Other** / **Unsorted** -- if you can't name it, you haven't understood it. Go back and read the file contents.
- **General** / **Common** / **Shared** -- shared by whom? General to what?
- **Resources** / **Assets** / **Materials** -- these are filler words. "Design resources" is "Design-Assets". "Tax materials" is "Finance/Taxes".
- **Archive** / **Old** / **Legacy** -- age is not a category. A 2018 tax return goes in Finance/Taxes, not "Archive".
- **Media** -- a video of your daughter's recital and a downloaded movie trailer have nothing in common. Name what the media is about.
- **Downloads** / **Inbox** / **New** -- these describe how files arrived, not what they are.
- **Untitled** / **Temp** / **tmp** -- if it exists, it means something. Figure out what.

If you find yourself reaching for any of these words, stop and read the files again. The real category name is hiding inside the files themselves.

The only exception: a subfolder inside a well-named parent (e.g., `3D-Printing/Assets/` or `Business/Pitch-Decks/<Project>/Screenshots/` is fine because the parent already gives context).

### Quality Gate: Taxonomy Failure Protection

Before you begin **any move**, enforce this gate. If any item fails, reroute taxonomy design automatically and refine before continuing.

1. **Semantic fidelity check**
   - If a folder name is vague (`Media`, `Personal`, `References`, etc.), replace with a specific, discoverable home.
   - `Projects` is only acceptable when the source actually contains distinct project roots or a deliberate project parent with project-specific children.
   - For every proposed top-level folder, keep at least three expected file examples and at least one concrete use case in the rationale. If confidence is weak, keep the folder out of top-level taxonomy and continue narrowing evidence.

2. **Project atomicity check**
   - Detect and preserve project roots as separate siblings unless evidence proves one should be nested inside another.
   - Indicators of a separate project include: README.md, .git, package.json, pyproject.toml, go.mod, Cargo.toml, Makefile, build scripts, or a folder name repeated in file paths.
   - If two folders each show project markers and different project names (e.g., `moving_map`, `chess-p2p`), keep both as distinct folders.

3. **Duplicate-category check**
   - Same intent split across duplicated parents (`Projects`, `Work/Projects`, `personal/Reading`, etc.) is a failure.
   - Merge only after content mapping is complete, and remove only the empty duplicate containers.

4. **Redundant nesting check**
   - No immediate parent-child pair should repeat the same semantic label (`X/X`, `Reading/Reading`, `Home/Home`).
   - Folder depth should not exceed 3 levels for personal taxonomy nodes unless it's an actual project internals hierarchy.

5. **Content-first placement check**
   - A media file is grouped by project/topic/folder owner first, not by extension.
   - If a folder appears to be a memory artifact (personal photos/videos) place in a memory-oriented bucket.
   - If it appears to support a named project, place in that project tree.

6. **Cross-domain tie-break check**
   - For files that could belong to multiple categories, keep it where the user would look first (housing doc first in Home, school item first in Kids/School, project collateral first in its project).

7. **Gate outcome**
   - If any check is uncertain, route it back through `Scout`/`Router`/`Gatekeeper` refinement and rerun Step 5.5 until the gate passes.
   - `low_confidence_count == 0` plus empty `active_gate_failures` is the controller's ready-to-execute condition.

## Autonomy

Execute the full workflow without pausing for user confirmation between steps.
The validation gates defined in this workflow are the only stopping points.
Do not ask "should I proceed?" or "should I continue?" at intermediate steps.
Report the final outcome when the workflow completes or a gate stops it.

This workflow is autopilot-first at the human level: no human review cycle is required by default.
Internal role handoffs still run: `Scout`, `Router`, `Gatekeeper`, and `Supervisor` must adjudicate ambiguity before execution, but they do so inside one run instead of through separate approval artifacts.
When running `semantic_scan.py --manifest --autopilot`, the script may perform internal refinement loops and draft candidate homes, but helper convergence does not authorize moves by itself.

## Workflow Overview

The process has three phases, each building on the last. Do not skip phases or combine them -- the quality of the final result depends on each phase informing the next.

### Phase 1: Inventory and Understand

Before touching a single file, build a complete picture of what exists and who the user is.

**Step 0: Create a rollback snapshot**

Capture a timestamped pre-run snapshot before any scans or moves. This snapshot is mandatory and serves as the rollback baseline if the reorganization needs to be reversed.

The default snapshot must stay lightweight and fast:

- Always capture structure, file inventory, and metadata manifests.
- Always create a run lock and update it through the workflow.
- Do **not** create a full mirror copy of the target tree during a normal run.
- Use reversible move ledgers and snapshot trash for non-interactive cleanup instead of paying the cost of a full-copy mirror up front.

```bash
cd <target-folder>
mkdir -p .tidy-folder-snapshots
snap="$(date +%Y%m%d_%H%M%S)"
SNAP_DIR=".tidy-folder-snapshots/$snap"
mkdir "$SNAP_DIR"
LOCK_FILE=".tidy-folder-snapshots/active-run.lock.json"

cat > "$LOCK_FILE" <<EOF
{"run_id":"$snap","started_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)","updated_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)","phase":"preflight","target_folder":"$(pwd)"}
EOF

# Structure and file inventory (human-readable)
find . \
  \( -path './.git' -o -path './.tidy-folder-snapshots' \) -prune \
  -o -print | sort > "$SNAP_DIR/tree.txt"
find . \
  \( -path './.git' -o -path './.tidy-folder-snapshots' \) -prune \
  -o -type f -print | sort > "$SNAP_DIR/files.txt"

# Lightweight metadata with size and mtime for deterministic verification
find . \
  \( -path './.git' -o -path './.tidy-folder-snapshots' \) -prune \
  -o -type f -exec sh -c 'stat -f "%N|%z|%m|%a" "$1"' _ {} \; | sort > "$SNAP_DIR/file-metadata.tsv"

cp "$SNAP_DIR/files.txt" "$SNAP_DIR/.tidy-folder-pre-run-files.txt"
cp "$SNAP_DIR/file-metadata.tsv" "$SNAP_DIR/.tidy-folder-pre-run-metadata.tsv"
mkdir -p "$SNAP_DIR/trash"
```

If this file set is present, a rollback candidate exists. Before finishing a session, keep it with the folder as `./.tidy-folder-snapshots/` and do not delete it automatically at the end of the run.
Rollback should use the pre-run inventory plus the move/deletion ledger from the run. Non-interactive cleanup must remain reversible by routing removals into the snapshot trash rather than permanent erase during the active run.

### Run Lock and Lease

The no-overlap rule must be operational, not aspirational:

- `Supervisor` must create `./.tidy-folder-snapshots/active-run.lock.json` before scanning.
- The lock must include at least: `run_id`, `target_folder`, `phase`, `started_at`, `updated_at`, and `owner`.
- Update `updated_at` at every phase transition and during long scans or move batches.
- If a lock exists and was updated recently, abort the new run immediately.
- If a lock is stale beyond the local lease threshold, write a takeover record into the new snapshot, replace the lock, and continue non-interactively.
- `Executor` must refuse to move files if the active lock no longer matches the current `run_id`.
- On success, block, or abort, write the final status artifact and remove the active lock.

**Step 1: Scan the folder structure**

Map everything -- folder names, file counts, nesting depth, file types. Use commands like:
```bash
# Top-level folders with file counts
for dir in */; do echo "$(find "$dir" -type f ! -name '.DS_Store' | wc -l) files: $dir"; done

# Loose files at root
find . -maxdepth 1 -type f ! -name '.*'

# Nesting depth check (anything > 3 levels is a red flag)
find . -type d -mindepth 4
```

**Step 2: Inspect actual file contents**

Filenames lie. A folder called "Academic-Papers" might contain kids' health records, tax forms, and appliance manuals mixed in with real papers. For PDFs, extract the first page text:
```bash
pdftotext file.pdf - -l 2 | head -20
```
For spreadsheets, read the header row. For images, note the naming patterns (timestamps suggest phone photos, descriptive names suggest downloads). For opaque filenames (UUIDs, hashes), check file size and type as clues.

For images and videos, sample the visible content and look for covers, screenshots, slides, logos, UI, or branding; those usually indicate a project or business owner rather than a photo-library home. For audio, read tags and any generated metadata before assuming it is just a song or voice memo.

This step is what separates a good reorganization from a bad one. The previous sorting attempt in this user's Downloads failed precisely because it categorized by file extension rather than reading what the files actually contained.

**Step 3: Deterministic ambiguity resolution**

Based on what you found, resolve ambiguities using evidence-derived rules and tie-breakers:

- If recurring personal names co-occur with school keywords, route to `Kids` leaves (`School`, `Health`, etc.) by strongest co-occurrence.
- If recurring project/product names co-occur across files and directories, split into sibling project leaves using deterministic naming.
- If 3D-printing signals exist but project ownership is weak, keep assets in `Projects` until stronger repeat evidence justifies dedicated `3D-Printing`.
- If a file already sits under an existing taxonomy node (e.g., `moving_map`, `chess_p2p`, previously-used business/client roots), prefer that node unless new evidence clearly points elsewhere.
- If multiple files share strong content signals but no existing home exists (e.g., many CSVs with matching headers, recurring domain terms, common identifiers, or repeated author/project tags), infer a candidate project or domain leaf.
  - Run a short content pass over those files before moving anything:
    - Parse headers/keys for structured files (`CSV`, `JSON`, `XML`, `Parquet`, etc.).
    - Extract top recurring tokens from filenames and embedded text.
    - Compare candidate labels against the existing taxonomy; if no parent exists, create one.
  - Create a new node only when confidence is durable:
    - at least 2 files share ≥2 high-signal signals (header/title/domain/owner terms), and
    - no higher-confidence assignment exists for those files.
  - Treat the inferred node as provisional in manifest pass 1, then verify stability in pass 2 before finalizing.

The goal is to infer the user's life domains so the taxonomy aligns with likely search behavior.

**Step 4: Check for existing organization patterns**

If the user has other organized folders (e.g., a Documents folder alongside a messy Downloads), inspect those structures first. Existing taxonomy is high-confidence signal: reuse those labels and boundaries when they match the current evidence, and only split/rename when evidence is stronger than prior structure.

Remember that an existing folder tree is often already semantically coherent even when it contains many file types. A project folder may mix docs, images, exports, audio, binaries, and source files because the hierarchy itself encodes meaning. Treat that subtree as a unit unless the inventory shows clear evidence that some files belong somewhere else.

### Phase 2: Design and Execute the Taxonomy

**Step 5: Propose the taxonomy**

Design only as many top-level categories as the inventory clearly supports. Small folders may need only 1-5 top-level homes; larger mixed archives may need more. Do not force a target count. Within each category, prefer the most specific stable subfolder that the inventory supports. Do not default to generic child folders like `Images`, `Media`, `Stuff`, or `Misc`; choose role-based or project-based names that tell the user what is inside. If the inventory reveals a repeated project or product name, create a project-specific home before falling back to a broader bucket.

Publish the taxonomy proposal internally with a brief description of what goes in each. Possible domains when the evidence supports them:

- **Kids** -- school records, health records, educational materials, activities
- **Family** -- trips, housing/leases, shared family documents, legal records
- **Career** -- resumes, work reimbursements, professional certifications
- **Finance** -- taxes, mortgage, banking, investment statements
- **Business** -- startup materials, pitch decks, branding, pricing research
- **Health** -- medical records, lab results, nutrition research, prescriptions
- **Home** -- product manuals, hardware photos, appliance docs, home improvement
- **Projects** -- only when the source actually contains real project roots or repeated project-specific materials
- **3D-Printing** -- models, slicing files, reference shapes (if applicable)
- **Photos** -- only for genuine memory photos and event snapshots; not project collateral
- **Reading** -- books, academic papers, research (actual intellectual reading)
- **Dev-Tools** -- downloaded libraries, frameworks, browser tools, SDKs

These are examples. The actual categories should emerge from the inventory, not from a template. `Projects` is a valid option only if projects are actually present in the source. A musician might need `Music`. A photographer might need `Client-Work`. A student might need `Courses`.

If a group of files shows coherent shared structure (e.g., repeated CSV schema columns, shared report titles, recurring partner names, common tags) and no existing top-level node matches, the taxonomy should grow upward: add a new higher-level node for that inferred domain, then place files under it (or under a project leaf beneath it).

Example:
- If several `CSV` files share `order_id`, `vendor_id`, `ship_date`, and `account_code`, and nothing in the current tree fits `Finance`/`Business`/`Projects`, add `Operations` or `Work/Operations` first, then place the CSV set under a specific child like `Operations/Reporting`.

**Self-check before proposing:** Review every proposed category name against the Banned Words List above. If any category could be replaced with a more specific name that tells the user what's actually inside, replace it. The test: if someone sees only the folder name with zero context, can they predict at least 3 files that would be inside? "Finance" -- yes (taxes, bank statements, mortgage docs). "Data" -- no (data about what?). "Resources" -- no (resources for what?). If a project name repeats across several files, prefer that project name over a generic bucket. If the file is a screenshot, cover, mockup, trailer, demo recording, or generated image for a named project, classify it by the project, not by the medium.

**Quality gate required before moving anything**: run the "Taxonomy Failure Protection" checks from above (semantic fidelity, project atomicity, duplicate-category, redundant nesting, content-first placement, and cross-domain tie-break) and document which checks passed or what remains ambiguous.

If pre-existing folders already encode a structure, treat those as starting taxonomy anchors, then run the manifest loop against that prior structure before creating new roots.

Before moves begin, create a draft placement manifest as the shared working artifact:

```bash
cd /Users/tyemirov/Development/agentSkills/tidy-folder
python3 ./scripts/run_tidy_folder.py <target-folder>
```

The controller writes its draft manifest and handoff records into `./.tidy-folder-snapshots/<snapshot_id>/` inside the target folder, including `tree.txt`, `files.txt`, `file-metadata.tsv`, `manifest.json`, `draft-actions.json`, `handoffs/00-supervisor.json`, and the per-phase handoff files for preflight, scout, router, gatekeeper, executor, and audit. When execution runs, it also writes `move-ledger.json` plus a post-move audit manifest. Restore runs write `restore-report.json`. These artifacts are the run log and rollback contract.

Build the manifest as an iterative artifact:
- Round 1 may be helper-produced and must include: source path, proposed destination or candidate homes, evidence source list, and attribution source (`existing_taxonomy`, `filename`, `content`, `metadata`, `ocr`).
- `Router` must turn helper evidence into auditable destination decisions with explicit rationale in the router handoff.
- If an entry is still low-confidence after reconciliation, keep `proposed_destination` empty or keep it explicitly blocked; do not auto-pretend the helper resolved it.
- Use existing taxonomy as round seeds for scoring; then let the workflow reconcile helper proposals in passes.
- Continue automatic refinement through the capped pass budget as needed, but execution stays blocked until the gatekeeper handoff is clear.

Hard execution gate:
- Re-run helper evidence passes after each reconciliation when they add value.
- Execute moves only when the current run reports `low_confidence_count == 0` and `active_gate_failures == []`.
- Snapshot inventory plus `move-ledger.json` and `--restore-snapshot <snapshot_id>` are the rollback mechanism.

- For each candidate file/folder group, record:
  - Source path
  - Proposed destination path, or an empty destination when refinement is still required
  - Why this destination is correct (content signal + category rationale)
  - Confidence (High/Medium/Low)
  - Evidence used (filenames, metadata, OCR/text/headers, extension context)
  - Alternatives considered and why rejected
  - Open ambiguities requiring refinement
- Keep the manifest deduplicated; one source path maps to one destination.
- Do not execute moves while any low-confidence blocker remains:
  - Duplicate top-level category intent
  - Repeated/needless nesting (`X/X`)
  - Project roots merged without evidence
  - Proposal uses banned vagueness words at destination
  - Any `low_confidence` destination
- If there are blockers, iterate Step 5.5 automatically and repair the taxonomy before continuing.

If the manifest is written and validated, proceed with move execution only when no blockers remain. Router and Gatekeeper handoffs are audit records, not separate approval checkpoints.

## Role-Based Orchestration Protocol

Use this protocol whenever you involve sub-agents in execution. This protocol is the control plane. When sub-agents are unavailable or unnecessary, the controller must still persist the same role handoff artifacts locally so the workflow stays auditable.

### Supervisor (Flow Controller)

- Owns pass count, manifests, refinement iterations, and snapshot policy.
- Creates and tracks `supervisor_handoff` records before each phase transition.
- Never allows move actions while blockers remain.
- Treats helper manifests, confidence scores, and fallback suggestions as advisory only.
- Owns snapshot restoration through `--restore-snapshot <snapshot_id>`.

### Scout Agent

- Scans assigned path slices for evidence only.
- Returns structured evidence packets (path context, text signals, metadata, OCR/vision hints, existing-taxonomy anchors).
- May call helpers to accelerate extraction, but does not convert helper output into final placement decisions.
- Does not create final destination decisions.

### Router Agent

- Converts scout evidence into auditable manifest entries.
- Builds proposals with:
  - deterministic destination,
  - tie-break rationale,
  - top candidates and alternatives,
  - confidence band.
- Applies specificity ladder and existing taxonomy anchors before proposing generic media/doc buckets.
- May accept, refine, or override helper candidate homes, but must explain overrides and unresolved ambiguity.

### Gatekeeper Agent

- Blocks execution on any of:
  - helper-reported low confidence that remains unresolved after reconciliation,
  - placement modes that are not high-confidence,
  - unresolved `needs_refinement` entries,
  - taxonomy gate failures (vague top-level intent, duplicate semantics, redundant nesting, project split violations, shallow depth violations, cross-domain tie-break errors).
- Must inspect raw `Scout` evidence independently, not just `Router` rationale.
- Must independently review:
  - every deletion candidate,
  - every sensitive bucket (`Health`, `Finance`, `Legal`, `Identity`, kids records),
  - and a representative sample from each major proposed home, including at least one weak-signal example.
- Treats helper-reported low confidence and helper gate failures as strong signals, but confirms or overrides them explicitly.
- Returns explicit fix packets and a re-run trigger; does not allow ambiguous moves.

### Executor Agent

- Applies only current-run draft actions when the gatekeeper handoff is clear.
- Performs idempotent, deterministic mv operations and canonical cleanup.
- Writes `move-ledger.json` for restore and audit instead of waiting on separate approval files.
- Reports action deltas and any drift before handoff returns to Supervisor.

Handoff requirements:
- `target_folder`
- `snapshot_id`
- `manifest_path`
- `pass`
- `scout_evidence_paths`
- `helper_findings`
- `decision_rationale`
- `active_gate_failures` (must be empty at execution time)
- `draft_actions`

Parallelism rule:
- Do not run overlapping scan/execution cycles on the same directory.
- Parallel scouts may only work on disjoint path subsets.
- Consolidate and rescan once before any move authorization.

**Step 5.5: Reconcile the emerging taxonomy**

Before committing the first move set, inspect the structure that has started to emerge from the actual files. This is the reconciliation cycle that turns a broad first pass into a specific final taxonomy.

This is an iterative cycle. Treat the taxonomy as a working hypothesis, then let the files push back on it:

- Merge thin or duplicate categories that are really the same home.
- Split overloaded categories when repeated evidence suggests a stable leaf folder.
- Reassign files from a broad parent into a new leaf when accumulated understanding makes that leaf the more specific and more searchable home.
- Prefer repeated evidence or strong cross-file context over a one-off guess before creating a new leaf.
- Re-run the audit against the new leafs so the earlier provisional placements can be corrected before anything is finalized.
- Continue Step 5.5 cycles until the gatekeeper handoff is clear or the remaining entries stay explicitly blocked.
- Keep each iteration recorded in the manifest as an explicit pass with the exact rationale for each file-level move so the cycle is auditable and deterministic.

Examples of healthy refinement:
- `Projects` becomes `Projects/MediaOps`, `AI-Art`, or another project-specific leaf once enough files point there.
- `Business` becomes `Business/Pitch-Decks` or `Business/Client-Work` instead of staying a broad catch-all.
- `Photos` may split into subject- or event-specific leafs, but only when the files clearly support that distinction.

This cycle is allowed to reassign files that were provisionally grouped under broader parents. The goal is the most specific stable home, not the first plausible home.

If later auditing reveals that a broad category should actually be split differently, go back to this step, update the taxonomy, and reclassify the affected files before finalizing the structure. Continue until the taxonomy and the file placements converge.

**Step 6: Move and rename**

Use the validated placement manifest from Step 5 as the execution plan.

This step runs only when Step 5/5.5 has completed with no unresolved blockers.

Execute the reorganization in a single logical pass per category, after the emerging taxonomy has been reviewed and refined. Key principles:

- **Fix typos**: "DIsney with Charachters" becomes "Disney-Characters"
- **Normalize names**: Use dashes instead of spaces, capitalize meaningfully. "beercss-3.8.0" becomes "BeerCSS-3.8.0"
- **Flatten unnecessary nesting**: If a path is `Sorted/Archive/Legacy/Archive/Directory_Downloads/Directory_Archive/`, something went wrong. No file should be more than 3 levels deep from the root unless it's a code project with its own internal structure
- **Preserve project internals**: Code repos, node_modules, build artifacts, and already coherent project trees -- leave their internal structure alone. Only move the top-level project folder or the clearly misfiled leaf, not the meaningful internal hierarchy.
- If a manifest entry resolves to a project home because of a detected project root, preserve the relative subtree beneath that project root during execution. Do not flatten `src/`, `components/`, or other internal paths into the project root.
- **Handle duplicates**: If two folders contain the same content (e.g., material-web and material-web-main), keep one canonical project root and remove the duplicate deterministically.
- **Promote discovered leafs**: If the accumulated understanding revealed a more specific leaf folder during Step 5.5, move files into that leaf rather than leaving them in a broad parent.

Use `mv` not `cp` to avoid doubling disk usage. If a move fails or times out on large directories, break it into smaller operations.

### Phase 3: Deep Content Audit

This is what makes the reorganization actually good rather than just superficially tidy. After the initial categorization, go back through each category and verify that every file is where the user would look for it.

Audit groups, not every file individually, unless the group is mixed-signal or high-risk:

- Cluster by proposed home, repeated tokens, source subtree, and file role.
- For a stable cluster, inspect representative members:
  - the strongest-signal file,
  - the weakest-signal file,
  - and at least one additional sample when the cluster is large.
- Escalate to full-file review only for:
  - sensitive domains,
  - deletion candidates,
  - mixed-signal clusters,
  - or clusters where representative review finds drift.
- Once a cluster is stable, accept the cluster and move on instead of rereading every member.

**Step 7: Audit each category**

For each category, validate each file by signal strength and deterministic tie-breakers: does this file belong here, or should it be moved elsewhere?

Common misclassifications to catch:
- Kids' documents filed under generic "Personal" or "Documents"
- Financial documents (taxes, mortgage) mixed into "Career"
- Product manuals categorized as "Reading"
- Health records categorized as "Academic Papers" because they're PDFs
- Educational worksheets for children filed under "3D Printing" because they're about shapes
- Home-related documents (leases, HOA) scattered across "Legal", "Finance", "Personal"

**Step 8: Resolve the cross-cutting concerns**

Some files touch multiple domains. A lease is both "Family/Housing" and "Finance". A child's school registration form is both "Kids/School" and "Legal". The rule: **put it where the user would look first.** A lease goes in Family/Housing because when someone thinks "where's my lease?", they think about their home, not their finances. The school form goes in Kids/School because it's about the child's enrollment, not a legal matter. A business project image, screenshot, mockup, or generated visual goes with the business project first, because the user will look up the project name before they look for `Photos`. For media files, the same rule applies: a polished cover image, promo render, demo clip, or recorded walkthrough belongs with the project it supports unless it is clearly a personal memory artifact.

If Step 8 reveals a better boundary between parents and leaf folders, feed that back into Step 5.5 and re-run the affected classifications before moving on. The audit is meant to refine the taxonomy, not merely validate it.

**Step 9: Identify and handle junk**

Every folder accumulation has genuine junk: saved webpage assets (.js, .css from a "Save Page As"), unidentifiable hash-named files, duplicate compressed versions of the same photo. Handle these:
- Saved webpage assets (JS, CSS, bundled files): treat as deletable only when a matching saved-page companion exists and the asset folder contains only derivative web-export files. If independent content signals exist, keep them.
- Exact duplicates: remove only when they are byte-identical or otherwise provably identical by deterministic evidence.
- Duplicate photos (file.heic + file.jpeg of same image): auto-remove only when the files are clearly the same capture and one is a lower-fidelity derivative. If the equivalence is not deterministic, keep both or route them to a reversible duplicate-review area.
- Unidentifiable files (UUID names, no extension): try `file` command to identify; if still unclear, route to `Recovery/Unknown-Text` or `Recovery/Unknown-Binary` for later audit.
- Project collateral that merely looks like an image/video/audio file is not junk; keep it with the project unless it is clearly a disposable duplicate or explicitly discardable
- Empty folders: delete silently

Apply deterministic deletion rules only: generated web assets with matching companions, exact duplicates, and empty folders. Never pause for confirmation.
Non-interactive cleanup must still be reversible during the run: move removed items into `./.tidy-folder-snapshots/<snapshot_id>/trash/` with a deletion ledger instead of permanently erasing them during the active workflow.
Scripts may surface deletion candidates, but deletion decisions still belong to `Router`/`Gatekeeper`/`Executor`.

**Step 10: Present the final structure**

Show the complete tree with file counts. The user should be able to look at this and immediately know where to find anything they own. If a category name doesn't immediately tell you what's inside, rename it.
If the audit caused a taxonomy change, present the final tree that reflects the refined taxonomy, not the initial provisional one.

**Step 11: Restore from snapshot (if the run must be undone)**

This is required only if the reorganization needs to be reverted:

```bash
cd <target-folder>
SNAP_DIR=$(ls -1d .tidy-folder-snapshots/* | sort | tail -n 1)
echo "Use the run's move ledger to reverse mv operations."
echo "Restore any removed items from $SNAP_DIR/trash/ using the cleanup ledger."
```

After restoration, rerun Step 7 (audit) on a quick sample to confirm that the pre-run state was restored and then remove any newly created temporary folders only if intended.

## Things That Go Wrong (and how to avoid them)

**The file-type trap**: The strongest gravitational pull is to sort by extension. PDFs in one folder, images in another, spreadsheets in a third. Resist this. A PDF of a child's report card has nothing in common with a PDF of an academic paper except the container format. They belong in completely different places.

**The medium trap**: images, videos, and audio are not generic destinations. A project cover image, screenshot, or demo recording belongs with the project it supports, not in `Photos` or any other medium bucket.

**The visible-content trap**: do not ignore what the file shows just because the filename is generic. If the image shows a deck cover, product screenshot, logo, or project branding, that is project evidence and should drive the placement.

**The vague-name trap**: "Documents", "Data", "Files", "Resources", "Personal", "Misc" -- these are not categories, they're admissions that you didn't look hard enough. If you can't name a category specifically, you haven't understood the files inside it. Go back to Phase 1, read the actual file contents, and figure out what domain they belong to. Every file in a person's folder belongs to some concrete life domain -- their kids' school, their taxes, their hobby, their job. Find that domain and name the folder after it.

**Over-nesting**: `Family/Housing/Leases/2025/January/` is too deep. `Family/Housing/Leases/` with the files right there is fine. Humans don't think in 5-level hierarchies.

**Under-auditing**: The first pass will get 80% of files right. The remaining 20% -- the ones where the filename doesn't match the content -- are what determine whether the reorganization actually helps. Always do the deep content audit.

**Frozen first pass**: A provisional category is not final just because it was the first guess. If new evidence points to a clearer leaf folder, reassign the file there before you finish.

**Previous sorting attempts**: If someone (or another AI) has already tried to sort the folder, you'll likely find remnants: empty category folders, deeply nested archive structures, files moved into generic buckets. Don't build on top of these -- understand what the previous attempt did, rescue the files, and start fresh with your own taxonomy.
