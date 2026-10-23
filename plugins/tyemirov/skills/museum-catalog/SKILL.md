---
name: museum-catalog
description: "Catalog museum visits in Apple Photos on macOS only. Identify artworks from photographed labels or visual research. Save artwork metadata and organize visit photos."
deployment:
  include:
  - all
---

# Museum photo catalog (macOS only)

**Platform: macOS only.**
This workflow requires the local Apple Photos library and macOS automation.
Local OCR uses Apple Vision and AppKit through Swift.
Run the skill on the Mac that has access to the Photos library.

Use Apple Photos as the catalog.
The assistant identifies and verifies artworks.
The local helper reads the library, prepares previews, plans metadata changes, and verifies writes.
The helper does not identify artworks automatically.

## Private visit files

Select a private directory outside this skill and its repository for each visit.
Keep personal photos, inventories, manifests, ownership state, previews, and logs in that directory.
Use a new run directory for each inventory, plan, and apply log.
Keep the reviewed manifest and persistent ownership state at the visit root.
Read those private records before you continue an existing visit.

## Photo metadata

- Set **Title** to the verified artwork title alone.
- Keep artist, year, museum, and visit date out of **Title**.
- Keep an unknown title empty, or preserve an existing user title.
- For a photo of several distinct works, keep **Title** empty.
- Use **Caption** for verified facts about the exhibited object.
- Keep museum, visit date, and category text out of **Caption**.
- Prefer `Artist: …`, `Year: …`, and `Medium: …` on separate lines.
- Omit unknown facts.
- Add a short uncertainty note when necessary.
- Preserve existing user keywords.
- Add no duplicate title, artist, visit, or category keywords by default.
- Keep evidence, sources, label text, dimensions, edition research, and photo links in the private manifest.
- Include an unusual artwork fact in Photos only when useful and verified for the exhibited object.
- Give family and architecture photos no generic catalog text.
- Preserve user metadata on family and architecture photos.

A family photo can link to an artwork in the manifest without receiving that artwork title.
An unidentified artwork can have a short visual description in **Caption** when useful.

```text
Title: Daybreak
Caption:
Artist: Maxfield Parrish
Year: 1922
Medium: Oil on board
```

Read [the manifest reference](references/manifest.md) before you prepare a manifest or run the helper.

## Inspect a visit

1. List the current Photos folders and albums.
2. Select an explicit source ID for the visit.
3. Read current membership from Photos.
4. Save an inventory of photo IDs, metadata, album membership, and capture properties.
5. Prepare local previews from current rendered copies.
6. If a current render is unavailable, explicitly select a rendered export from Photos.
7. Preserve originals and edit history.
8. Keep personal photos local.
9. Use capture order to find possible adjacent labels.
10. Verify each artwork and label match from the image, signature, subject, and layout.
11. Link each identification to explicit photo IDs and a stable `work_id`.

A nearby label can describe a different work or several works.
Prefer photographed museum labels for facts about the exhibited object.
Compare OCR text with the label image.

For a missing label, use visual identification and current primary sources.
These sources can include museum, artist, gallery, or auction records.
Follow each source link before you use its contents as evidence.
Distinguish a visual match from a museum record for the exhibited object.
Use a date, material, or edition only when the evidence supports that exhibited version.

## Photo categories

- `Family & People`: a known family member appears in the image.
- **Artworks & Exhibits:** an artwork or exhibit appears without a family member.
- **Architecture & Museum Spaces:** a building, interior, grounds, or architectural model appears without a family member.

Family presence has priority over artwork and architecture.
Include partial figures, reflections, and background appearances when you examine images for family members.
Use user context, reference photos, or existing personal groups to identify family members.
An incidental stranger does not make an artwork photo a family photo.
If family identification is unresolved, put the photo in review.

Keep photos of labels in the source or a separate **Placards & Review** album.
Keep these photos outside the three subject categories.
Unresolved photos can remain in the source.
Keep **All Visit Photos** when requested or already present.
Respect a later user instruction to remove that album.
Preserve source photos and unrelated album membership.
Delete labels only when the user explicitly requests deletion for that visit.

## Organize albums

Create a museum and date folder inside **Art Collection** when appropriate.
Record the IDs and exact membership of albums that this workflow manages.
Before each update, inspect current membership in those albums.
Put each reviewed subject photo in exactly one subject category.
Preserve user additions outside the reviewed manifest.

Use supported Photos automation or the Photos interface to change album membership.
If the interface supports additions only, replace a managed album only with verified contents:

1. Create the replacement album.
2. Add the reviewed photo IDs.
3. Verify every member ID.
4. Replace only the old managed album container.
5. Record the new album ID.

Preserve unrelated albums and their contents.
If conflicts remain, report them.
An operation that only adds photos does not prove that category membership is disjoint.

## Apply metadata

1. Prepare the reviewed manifest.
2. Preview the metadata plan.
3. Apply the plan within the user's requested scope.
4. Inspect the reported status and skipped fields.
5. Verify the updated fields and preserved properties.
6. Report unresolved conflicts before you claim completion.

The helper writes only intended title and caption fields.
It preserves keywords, capture dates, locations, favorites, originals, edits, and album membership.
An empty field or an exact last-owned value can change.
Any other current value is a user edit to preserve and report.

Track the last successful value for each field separately.
Check each value immediately before its write.
Record each successful write in the journal and verify the result.
Keep the before, plan, and after records.
For an interruption, use the journal recovery command in the manifest reference.

With an unchanged manifest and source, a new plan must contain zero changes.
A corrected identification can update an exact skill-owned value.
After album organization, verify photo IDs, category coverage, disjoint categories, metadata, and preserved properties.
Report current counts, verified identifications, and unresolved cases.
Count label photos separately from identified artworks.
