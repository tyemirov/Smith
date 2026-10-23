# Identification manifest

Use one artwork record for each exhibited object and version within a visit.
Link each photo ID to that record.
Several views of the same object share one work ID.
A similar title or artist alone does not establish that two objects are the same.
Keep evidence and source links in the private manifest.
Keep source links out of Photos captions.

```json
{
  "visit": {"museum": "Museum name", "date": "YYYY-MM-DD"},
  "works": {
    "work-001": {
      "title": "Daybreak",
      "artist": "Maxfield Parrish",
      "year": "1922",
      "medium": "Oil on board",
      "identification": "label",
      "notes": "",
      "evidence": {
        "title": [{"label_photo_id": "LABEL-ID", "note": "Exact title visible"}],
        "artist": [{"label_photo_id": "LABEL-ID"}],
        "year": [{"label_photo_id": "LABEL-ID"}],
        "medium": [{"label_photo_id": "LABEL-ID"}]
      }
    }
  },
  "photos": [
    {"id": "ARTWORK-PHOTO-ID", "category": "artwork", "work_id": "work-001"},
    {"id": "SECOND-VIEW-ID", "category": "artwork", "work_id": "work-001"},
    {"id": "LABEL-ID", "category": "label", "work_id": "work-001"},
    {"id": "FAMILY-PHOTO-ID", "category": "family", "work_id": null},
    {"id": "BUILDING-PHOTO-ID", "category": "architecture", "work_id": null}
  ],
  "labels": [
    {"photo_id": "LABEL-ID", "entries": [{"work_id": "work-001", "transcription": "Verified label text"}]}
  ]
}
```

Supported categories are `family`, `artwork`, `architecture`, `label`, and `review`.
A photo links to one `work_id` or null.
Keep relationships for several works in `labels` or another private relationship record.
For a photo of several works, leave the Photos Title empty.
For an unidentified artwork, use `work_id: null`.
Add a short description in `notes` when useful.
Keep an artwork photo in the artwork category when a cropped label appears beside the primary subject.
Put photos of labels alone in the label category.

Identification values are `label`, `visual`, and `unverified`.
For an unverified title, use an empty or missing title field.
For a visual identification, include a short qualification in `notes`.
Each asserted title, artist, year, and medium needs evidence.
The helper verifies the evidence structure, not the correctness of an identification.
The assistant verifies each fact before it prepares a metadata plan.

Evidence can use these source fields:

- `label_photo_id`: the photo ID of a label.
- `photo_id`: the photo ID of a visible signature or inscription.
- `url`: a primary source URL.
- `note`: an optional explanation.

Use verified facts for dimensions, dates, species, and edition numbers.
Keep unknown values empty.

## Run the helper

Use macOS with Apple Photos, `osascript`, `sips`, Swift, and `uv`.
The helper verifies macOS before a command reads visit files or starts native tools.
Use `--help` on any platform to read the CLI usage.
Select an absolute skill path and a separate private visit directory.
Keep the visit directory outside the skill and its repository.
Replace the example paths and source IDs with the user's selected values.

```sh
MUSEUM_SKILL="/absolute/path/to/museum-catalog"
PRIVATE_VISIT="/absolute/private/path/to/visit"
PRIVATE_RUN="$PRIVATE_VISIT/runs/first-run"
mkdir -p "$PRIVATE_RUN"
uv run --script "$MUSEUM_SKILL/scripts/museum_catalog.py" --help
uv run --script "$MUSEUM_SKILL/scripts/museum_catalog.py" sources --out "$PRIVATE_RUN/sources.json"
uv run --script "$MUSEUM_SKILL/scripts/museum_catalog.py" inventory --album-id SOURCE_ID --out "$PRIVATE_RUN/inventory.json"
uv run --script "$MUSEUM_SKILL/scripts/museum_catalog.py" previews --snapshot "$PRIVATE_RUN/inventory.json" --renders "$PRIVATE_VISIT/render-paths.json" --out "$PRIVATE_RUN/previews"
swift "$MUSEUM_SKILL/scripts/ocr_labels.swift" "$PRIVATE_RUN/previews/SELECTED_LABEL.jpg"
uv run --script "$MUSEUM_SKILL/scripts/museum_catalog.py" plan --snapshot "$PRIVATE_RUN/inventory.json" --manifest "$PRIVATE_VISIT/manifest.json" --out "$PRIVATE_RUN/plan.json"
uv run --script "$MUSEUM_SKILL/scripts/museum_catalog.py" apply --plan "$PRIVATE_RUN/plan.json"
uv run --script "$MUSEUM_SKILL/scripts/museum_catalog.py" apply --plan "$PRIVATE_RUN/plan.json" --apply --log "$PRIVATE_RUN/apply.json" --state "$PRIVATE_VISIT/state.json"
```

Create the reviewed manifest before the `plan` command.
The preview command prints proposed metadata changes without a write to Photos.
The `--apply` flag explicitly permits the reviewed writes.

For the first plan, omit `--state` until the state file exists.
For later plans, pass `--state "$PRIVATE_VISIT/state.json"` to the `plan` command.
Use a fresh run directory for each update.
Use a fresh log path for each apply operation.

Use `--folder-id FOLDER_ID` instead of `--album-id` to read all photos in a visit folder's albums.
The helper removes duplicate photo IDs from this inventory.
The Photos API exposes scriptable user albums, not Shared Albums.

The `render-paths.json` file maps photo IDs to trusted local paths for current rendered copies.
The helper reports previews without a render as `needs-current-render`.
Use `--allow-export` to obtain missing edited renders from Photos.
Photos can download these copies from iCloud.
Select only the necessary source photos for large exports.
The helper uses `sips` to create smaller preview copies.
It preserves the supplied render files.

OCR writes JSON lines to standard output.
OCR does not identify artworks by itself.
The assistant reviews the images, identifies artworks, and verifies the evidence.

After each apply operation, inspect the reported status and skipped fields.
A `partial` status indicates preserved conflicts.
Report those conflicts before you claim that all metadata is updated.
The helper records ownership only for confirmed writes.

## Recover an interrupted apply

The apply log and adjacent `.writes.json` journal record successful field writes.
Use the same reviewed plan and log for recovery:

```sh
uv run --script "$MUSEUM_SKILL/scripts/museum_catalog.py" recover --plan "$PRIVATE_RUN/plan.json" --log "$PRIVATE_RUN/apply.json" --state "$PRIVATE_VISIT/state.json"
```

Recovery checks live values before it restores ownership records.
Inspect the recovery status and skipped fields.
Then take a fresh inventory, generate a new plan, and preview that plan.

State belongs to a visit.
It records exact previous values, not general permission to replace fields.
The helper does not organize albums or delete photos.
The assistant reconciles reviewed membership through Photos and records managed album IDs in the private visit directory.
