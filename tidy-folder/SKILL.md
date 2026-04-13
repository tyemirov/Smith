---
name: tidy-folder
description: |
  Reorganize messy folders into a clean, discoverable structure based on the user's life domains and interests -- not by file type. Use this skill whenever the user asks to organize, tidy, clean up, sort, or declutter any folder or directory. Also trigger when users mention their Downloads folder is a mess, want to restructure a project directory, need to make files easier to find, or describe any folder as "chaotic", "cluttered", or "hard to navigate". This skill applies to any directory -- Downloads, Documents, project folders, shared drives, photo libraries, or any other folder the user wants organized.
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

## Recommended Tooling

Use the `scripts/semantic_scan.py` helper when it is available. Its job is to gather evidence, not to make final decisions:

- It runs through `uv` and installs its Python dependencies automatically.
- Its Python baseline uses `pypdf`, `Pillow`, `mutagen`, and `openpyxl` to cover the common portable cases: PDF text, image metadata, audio/video tags, and spreadsheet previews.
- File type and MIME detection.
- Text previews from PDFs, documents, spreadsheets, CSV, JSON, and plain text.
- Metadata from images and media files.
- OCR or frame-grab text when local tools are present.
- Candidate homes with evidence and confidence.
- The contract is to infer a complete taxonomy end-to-end with no manual routing decisions.

Use `scripts/run_tidy_folder.py` for the full end-to-end workflow when you need the runtime contract, not just the evidence collector. It creates the rollback snapshot, persists the manifest, emits supervisor/gatekeeper handoff artifacts, and can optionally execute approved moves once the gates are green.

### Dependency and execution model

- This skill must use `uv` for Python execution.
- Do not install deps with `pip`, `pipx`, or global `venv` workflows for this script.
- Use a self-contained evidence-only run:

```bash
cd /Users/tyemirov/Development/agentSkills/tidy-folder
/opt/homebrew/bin/uv run ./scripts/semantic_scan.py /path/to/folder --manifest --autopilot
```

- Use the controller for the full orchestrated workflow:

```bash
cd /Users/tyemirov/Development/agentSkills/tidy-folder
python3 ./scripts/run_tidy_folder.py /path/to/folder
python3 ./scripts/run_tidy_folder.py /path/to/folder --execute
```

- The script uses a `uv` shebang (`#!/usr/bin/env -S uv run --with torch --with torchvision --script`) and declares Python requirements inline, so dependencies are resolved automatically.
- Vision mode is opt-in and explicit (recommended for images/videos):

```bash
uv run ./scripts/semantic_scan.py /path/to/folder --manifest --autopilot --vision
uv run ./scripts/semantic_scan.py /path/to/folder --manifest --autopilot --vision --vision-provider openai
```

- Vision dependencies are available via the `uv` launcher; enable multimodal captioning explicitly with `--vision`. Use `--vision-provider openai` to run image/video understanding through an API model (requires `OPENAI_API_KEY`) instead of local BLIP/CLIP-style captioning.

Native tools like `ffmpeg`, `pdftotext`, `tesseract`, `mdls`, `file`, `strings`, and `antiword` are optional accelerators. If a machine does not have them, the scanner still works, but some files will stay low-confidence until enough evidence is available.

Treat the script as an evidence collector. The skill produces the inferred taxonomy without user intervention.
- `needs_review` is not part of the execution contract. Files are flagged as `low_confidence` and fed through additional automatic refinement passes until `low_confidence` is fully resolved.
- Any `low_confidence` classification is a hard blocker. No moves are allowed until the manifest reports `low_confidence_count: 0`.
- Low-confidence manifest entries are non-routable by design: keep their evidence and candidates, but leave `proposed_destination` empty until refinement resolves them.

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
   - If a folder name is vague (`Projects`, `Media`, `Personal`, `References`, etc.), replace with a specific, discoverable home.
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
   - If any check is uncertain, resolve it with a deterministic refinement pass and rerun Step 5.5 until the gate passes and `low_confidence_count` is zero.

## Autonomy

Execute the full workflow without pausing for user confirmation between steps.
The validation gates defined in this workflow are the only stopping points.
Do not ask "should I proceed?" or "should I continue?" at intermediate steps.
Report the final outcome when the workflow completes or a gate stops it.

This workflow is autopilot-first: no human review cycle is required. Low-confidence placements are emitted in the manifest as actionable refinement candidates and are iterated automatically to raise confidence to zero before finalization.
**Hard stop rule:** any non-zero low-confidence count is a hard failure for execution; no file moves occur until `low_confidence_count` reaches zero.
When running `semantic_scan.py --manifest --autopilot`, the script now performs an internal refinement loop: it uses high-confidence placements from prior passes as additional taxonomy seeds, then re-runs up to a capped number of passes until low-confidence count stabilizes or reaches zero.

## Workflow Overview

The process has three phases, each building on the last. Do not skip phases or combine them -- the quality of the final result depends on each phase informing the next.

### Phase 1: Inventory and Understand

Before touching a single file, build a complete picture of what exists and who the user is.

**Step 0: Create a rollback snapshot**

Capture a timestamped pre-run snapshot before any scans or moves. This snapshot is mandatory and serves as the rollback baseline if the reorganization needs to be reversed.

```bash
cd <target-folder>
mkdir -p .tidy-folder-snapshots
snap="$(date +%Y%m%d_%H%M%S)"
SNAP_DIR=".tidy-folder-snapshots/$snap"
mkdir "$SNAP_DIR"

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

# Optional deterministic rollback payload (full content copy). Keep this if you want to
# revert changes by restoring files, not just auditing deltas.
mkdir -p "$SNAP_DIR/full-copy"
rsync -a --delete \
  --exclude='.git' \
  --exclude='.tidy-folder-snapshots' \
  . "$SNAP_DIR/full-copy"/

cp "$SNAP_DIR/files.txt" "$SNAP_DIR/.tidy-folder-pre-run-files.txt"
cp "$SNAP_DIR/file-metadata.tsv" "$SNAP_DIR/.tidy-folder-pre-run-metadata.tsv"
```

If this file set is present, a rollback candidate exists. Before finishing a session, keep it with the folder as `./.tidy-folder-snapshots/` and do not delete it until the user confirms completion.
If rollback is required later, only the `full-copy` snapshot supports guaranteed restoration.

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

Design 8-15 top-level categories based on life domains. Within each category, prefer the most specific stable subfolder that the inventory supports. Do not default to generic child folders like `Images`, `Media`, `Stuff`, or `Misc`; choose role-based or project-based names that tell the user what is inside. If the inventory reveals a repeated project or product name, create a project-specific home before falling back to a broader bucket.

Publish the taxonomy proposal internally with a brief description of what goes in each. Common domains (adapt to the specific user):

- **Kids** -- school records, health records, educational materials, activities
- **Family** -- trips, housing/leases, shared family documents, legal records
- **Career** -- resumes, work reimbursements, professional certifications
- **Finance** -- taxes, mortgage, banking, investment statements
- **Business** -- startup materials, pitch decks, branding, pricing research
- **Health** -- medical records, lab results, nutrition research, prescriptions
- **Home** -- product manuals, hardware photos, appliance docs, home improvement
- **Projects** -- code repos, technical projects, data projects
- **3D-Printing** -- models, slicing files, reference shapes (if applicable)
- **Photos** -- memory photos and event snapshots organized by event/subject, not date; not project collateral
- **Reading** -- books, academic papers, research (actual intellectual reading)
- **Dev-Tools** -- downloaded libraries, frameworks, browser tools, SDKs

These are examples. The actual categories should emerge from the inventory, not from a template. A musician might need "Music". A photographer might need "Client-Work". A student might need "Courses".

If a group of files shows coherent shared structure (e.g., repeated CSV schema columns, shared report titles, recurring partner names, common tags) and no existing top-level node matches, the taxonomy should grow upward: add a new higher-level node for that inferred domain, then place files under it (or under a project leaf beneath it).

Example:
- If several `CSV` files share `order_id`, `vendor_id`, `ship_date`, and `account_code`, and nothing in the current tree fits `Finance`/`Business`/`Projects`, add `Operations` or `Work/Operations` first, then place the CSV set under a specific child like `Operations/Reporting`.

**Self-check before proposing:** Review every proposed category name against the Banned Words List above. If any category could be replaced with a more specific name that tells the user what's actually inside, replace it. The test: if someone sees only the folder name with zero context, can they predict at least 3 files that would be inside? "Finance" -- yes (taxes, bank statements, mortgage docs). "Data" -- no (data about what?). "Resources" -- no (resources for what?). If a project name repeats across several files, prefer that project name over a generic bucket. If the file is a screenshot, cover, mockup, trailer, demo recording, or generated image for a named project, classify it by the project, not by the medium.

**Quality gate required before moving anything**: run the "Taxonomy Failure Protection" checks from above (semantic fidelity, project atomicity, duplicate-category, redundant nesting, content-first placement, and cross-domain tie-break) and document which checks passed or what remains ambiguous.

If pre-existing folders already encode a structure, treat those as starting taxonomy anchors, then run the manifest loop against that prior structure before creating new roots.

Before moves begin, create a placement manifest as a single source of truth:

```bash
cd /Users/tyemirov/Development/agentSkills/tidy-folder
python3 ./scripts/run_tidy_folder.py <target-folder>
```

The controller writes its manifest and handoff records into `./.tidy-folder-snapshots/<snapshot_id>/` inside the target folder, including `manifest.json`, `approved-actions.json`, and per-phase handoff files.

Build the manifest as an iterative artifact:
- Round 1 must include: source path, proposed destination, evidence source list, and attribution source (`existing_taxonomy`, `filename`, `content`, `metadata`, `ocr`).
- If an entry is still low-confidence, keep `proposed_destination` empty and surface candidate homes separately; do not emit a fallback destination.
- Use existing taxonomy as round seeds for scoring; then apply the manifest and regenerate in passes.
- Continue until `low_confidence` is **zero** and no high-confidence blockers remain.

Hard execution gate:
- Re-run the manifest pass after each reconciliation if `low_confidence_count > 0`.
- Execute moves only when the manifest resolves to `low_confidence_count == 0`.

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

If the manifest is written and validated, proceed with move execution only when no blockers remain and `low_confidence_count == 0`.

## Multi-Agent Orchestration Protocol

Use this protocol whenever you involve sub-agents in execution. It is mandatory for multi-agent runs.

### Supervisor (Flow Controller)

- Owns pass count, manifests, refinement iterations, and snapshot policy.
- Creates and tracks `supervisor_handoff` records before each phase transition.
- Never allows move actions without a green gate from Gatekeeper.

### Scout Agent

- Scans assigned path slices for evidence only.
- Returns structured evidence packets (path context, text signals, metadata, OCR/vision hints, existing-taxonomy anchors).
- Does not create final destination decisions.

### Router Agent

- Converts scout evidence into manifest entries.
- Builds proposals with:
  - deterministic destination,
  - tie-break rationale,
  - top candidates and alternatives,
  - confidence band.
- Applies specificity ladder and existing taxonomy anchors before proposing generic media/doc buckets.

### Gatekeeper Agent

- Blocks execution on any of:
  - `low_confidence_count != 0`,
  - placement modes that are not high-confidence,
  - `needs_refinement` entries,
  - taxonomy gate failures (vague top-level intent, duplicate semantics, redundant nesting, project split violations, shallow depth violations, cross-domain tie-break errors).
- Returns explicit fix packets and a re-run trigger; does not allow ambiguous moves.

### Executor Agent

- Applies only Supervisor-approved, Gatekeeper-cleared manifest actions.
- Performs idempotent, deterministic mv operations and canonical cleanup.
- Reports action deltas and any drift before handoff returns to Supervisor.

Handoff requirements:
- `target_folder`
- `snapshot_id`
- `manifest_path`
- `pass`
- `low_confidence_count` (must be 0)
- `active_gate_failures` (must be empty)
- `approved_actions`

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
- Continue Step 5.5 cycles until the manifest reaches `low_confidence_count == 0`.
- Keep each iteration recorded in the manifest as an explicit pass with the exact rationale for each file-level move so the cycle is auditable and deterministic.

Examples of healthy refinement:
- `Projects` becomes `Projects/MediaOps`, `AI-Art`, or another project-specific leaf once enough files point there.
- `Business` becomes `Business/Pitch-Decks` or `Business/Client-Work` instead of staying a broad catch-all.
- `Photos` may split into subject- or event-specific leafs, but only when the files clearly support that distinction.

This cycle is allowed to reassign files that were provisionally grouped under broader parents. The goal is the most specific stable home, not the first plausible home.

If later auditing reveals that a broad category should actually be split differently, go back to this step, update the taxonomy, and reclassify the affected files before finalizing the structure. Continue until the taxonomy and the file placements converge.

**Step 6: Move and rename**

Use the validated placement manifest from Step 5 as the execution source of truth.

This step runs only when Step 5/5.5 has completed a fully validated manifest with `low_confidence_count == 0` and no active gate blockers.

Execute the reorganization in a single logical pass per category, after the emerging taxonomy has been reviewed and refined. Key principles:

- **Fix typos**: "DIsney with Charachters" becomes "Disney-Characters"
- **Normalize names**: Use dashes instead of spaces, capitalize meaningfully. "beercss-3.8.0" becomes "BeerCSS-3.8.0"
- **Flatten unnecessary nesting**: If a path is `Sorted/Archive/Legacy/Archive/Directory_Downloads/Directory_Archive/`, something went wrong. No file should be more than 3 levels deep from the root unless it's a code project with its own internal structure
- **Preserve project internals**: Code repos, node_modules, build artifacts, and already coherent project trees -- leave their internal structure alone. Only move the top-level project folder or the clearly misfiled leaf, not the meaningful internal hierarchy.
- **Handle duplicates**: If two folders contain the same content (e.g., material-web and material-web-main), keep one canonical project root and remove the duplicate deterministically.
- **Promote discovered leafs**: If the accumulated understanding revealed a more specific leaf folder during Step 5.5, move files into that leaf rather than leaving them in a broad parent.

Use `mv` not `cp` to avoid doubling disk usage. If a move fails or times out on large directories, break it into smaller operations.

### Phase 3: Deep Content Audit

This is what makes the reorganization actually good rather than just superficially tidy. After the initial categorization, go back through each category and verify that every file is where the user would look for it.

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
- Saved webpage assets (JS, CSS, bundled files): delete as deterministic web artifacts unless a meaningful companion is detected
- Duplicate photos (file.heic + file.jpeg of same image): keep a deterministic canonical image and route the duplicate to trash
- Unidentifiable files (UUID names, no extension): try `file` command to identify; if still unclear, route to deterministic holding bucket for later audit.
- Project collateral that merely looks like an image/video/audio file is not junk; keep it with the project unless it is clearly a disposable duplicate or explicitly discardable
- Empty folders: delete silently

Apply deterministic deletion rules only: generated web assets, exact duplicates, and empty folders. Never pause for confirmation.

**Step 10: Present the final structure**

Show the complete tree with file counts. The user should be able to look at this and immediately know where to find anything they own. If a category name doesn't immediately tell you what's inside, rename it.
If the audit caused a taxonomy change, present the final tree that reflects the refined taxonomy, not the initial provisional one.

**Step 11: Restore from snapshot (if the run must be undone)**

This is required only if the reorganization needs to be reverted:

```bash
cd <target-folder>
SNAP_DIR=$(ls -1d .tidy-folder-snapshots/* | sort | tail -n 1)
if [ -d "$SNAP_DIR/full-copy" ]; then
  rsync -a --delete "$SNAP_DIR/full-copy"/ ./
else
  echo "No full-copy snapshot available. Use file-level audit lists only."
fi
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
