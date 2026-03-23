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

If you find yourself reaching for any of these words, **stop and ask what the files actually are**. Read their contents. The real category name is hiding inside the files themselves.

The only exception: a subfolder inside a well-named parent (e.g., `3D-Printing/Assets/` is fine because the parent already gives context).

## Workflow Overview

The process has three phases, each building on the last. Do not skip phases or combine them -- the quality of the final result depends on each phase informing the next.

### Phase 1: Inventory and Understand

Before touching a single file, build a complete picture of what exists and who the user is.

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

This step is what separates a good reorganization from a bad one. The previous sorting attempt in this user's Downloads failed precisely because it categorized by file extension rather than reading what the files actually contained.

**Step 3: Quick targeted interview**

Based on what you found, ask 2-3 specific questions to resolve ambiguities. The scan should already reveal most of the context -- family members' names appear in files, job history shows up in resumes, hobbies are visible in project folders. Only ask about what you can't infer:

- "I see school docs for Alice and Peter -- are these your children? How old are they?" (not "Tell me about your family")
- "There are Everlight and Poodle-Scanner pitch decks -- are these your startup projects?" (not "What do you do for work")
- "I found 3D printing files mixed with code projects -- should those be separate categories?"

The goal is to understand the user's life domains so the taxonomy matches how they think.

**Step 4: Check for existing organization patterns**

If the user has other organized folders (e.g., a Documents folder alongside a messy Downloads), look at how they've already organized things. This reveals their natural mental model. Don't copy the structure blindly, but let it inspire the taxonomy. If they already have a "Kids" folder in Documents, that confirms "Kids" is a natural category for them.

### Phase 2: Design and Execute the Taxonomy

**Step 5: Propose the taxonomy**

Design 8-15 top-level categories based on life domains. Present them to the user with a brief description of what goes in each. Common domains (adapt to the specific user):

- **Kids** -- school records, health records, educational materials, activities
- **Family** -- trips, housing/leases, shared family documents, legal records
- **Career** -- resumes, work reimbursements, professional certifications
- **Finance** -- taxes, mortgage, banking, investment statements
- **Business** -- startup materials, pitch decks, branding, pricing research
- **Health** -- medical records, lab results, nutrition research, prescriptions
- **Home** -- product manuals, hardware photos, appliance docs, home improvement
- **Projects** -- code repos, technical projects, data projects
- **3D-Printing** -- models, slicing files, reference shapes (if applicable)
- **Photos** -- organized by event/subject, not date
- **Reading** -- books, academic papers, research (actual intellectual reading)
- **Dev-Tools** -- downloaded libraries, frameworks, browser tools, SDKs

These are examples. The actual categories should emerge from the inventory, not from a template. A musician might need "Music". A photographer might need "Client-Work". A student might need "Courses".

**Self-check before proposing:** Review every proposed category name against the Banned Words List above. If any category could be replaced with a more specific name that tells the user what's actually inside, replace it. The test: if someone sees only the folder name with zero context, can they predict at least 3 files that would be inside? "Finance" -- yes (taxes, bank statements, mortgage docs). "Data" -- no (data about what?). "Resources" -- no (resources for what?).

Wait for the user to approve before moving anything.

**Step 6: Move and rename**

Execute the reorganization in a single logical pass per category. Key principles:

- **Fix typos**: "DIsney with Charachters" becomes "Disney-Characters"
- **Normalize names**: Use dashes instead of spaces, capitalize meaningfully. "beercss-3.8.0" becomes "BeerCSS-3.8.0"
- **Flatten unnecessary nesting**: If a path is `Sorted/Archive/Legacy/Archive/Directory_Downloads/Directory_Archive/`, something went wrong. No file should be more than 3 levels deep from the root unless it's a code project with its own internal structure
- **Preserve project internals**: Code repos, node_modules, build artifacts -- leave their internal structure alone. Only move the top-level project folder
- **Handle duplicates**: If two folders contain the same content (e.g., material-web and material-web-main), note it for the user but don't delete without asking

Use `mv` not `cp` to avoid doubling disk usage. If a move fails or times out on large directories, break it into smaller operations.

### Phase 3: Deep Content Audit

This is what makes the reorganization actually good rather than just superficially tidy. After the initial categorization, go back through each category and verify that every file is where the user would look for it.

**Step 7: Audit each category**

For each category, list the actual files and ask: "Does this file belong here, or would the user look for it somewhere else?"

Common misclassifications to catch:
- Kids' documents filed under generic "Personal" or "Documents"
- Financial documents (taxes, mortgage) mixed into "Career"
- Product manuals categorized as "Reading"
- Health records categorized as "Academic Papers" because they're PDFs
- Educational worksheets for children filed under "3D Printing" because they're about shapes
- Home-related documents (leases, HOA) scattered across "Legal", "Finance", "Personal"

**Step 8: Resolve the cross-cutting concerns**

Some files touch multiple domains. A lease is both "Family/Housing" and "Finance". A child's school registration form is both "Kids/School" and "Legal". The rule: **put it where the user would look first.** A lease goes in Family/Housing because when someone thinks "where's my lease?", they think about their home, not their finances. The school form goes in Kids/School because it's about the child's enrollment, not a legal matter.

**Step 9: Identify and handle junk**

Every folder accumulation has genuine junk: saved webpage assets (.js, .css from a "Save Page As"), unidentifiable hash-named files, duplicate compressed versions of the same photo. Handle these:
- Saved webpage assets (JS, CSS, bundled files): delete unless the user specifically saved the page intentionally
- Duplicate photos (file.heic + file.jpeg of same image): note for the user, suggest keeping one
- Unidentifiable files (UUID names, no extension): try `file` command to identify, ask user if still unclear
- Empty folders: delete silently

Always ask before bulk-deleting. Present what you found and get confirmation.

**Step 10: Present the final structure**

Show the complete tree with file counts. The user should be able to look at this and immediately know where to find anything they own. If a category name doesn't immediately tell you what's inside, rename it.

## Things That Go Wrong (and how to avoid them)

**The file-type trap**: The strongest gravitational pull is to sort by extension. PDFs in one folder, images in another, spreadsheets in a third. Resist this. A PDF of a child's report card has nothing in common with a PDF of an academic paper except the container format. They belong in completely different places.

**The vague-name trap**: "Documents", "Data", "Files", "Resources", "Personal", "Misc" -- these are not categories, they're admissions that you didn't look hard enough. If you can't name a category specifically, you haven't understood the files inside it. Go back to Phase 1, read the actual file contents, and figure out what domain they belong to. Every file in a person's folder belongs to some concrete life domain -- their kids' school, their taxes, their hobby, their job. Find that domain and name the folder after it.

**Over-nesting**: `Family/Housing/Leases/2025/January/` is too deep. `Family/Housing/Leases/` with the files right there is fine. Humans don't think in 5-level hierarchies.

**Under-auditing**: The first pass will get 80% of files right. The remaining 20% -- the ones where the filename doesn't match the content -- are what determine whether the reorganization actually helps. Always do the deep content audit.

**Previous sorting attempts**: If someone (or another AI) has already tried to sort the folder, you'll likely find remnants: empty category folders, deeply nested archive structures, files moved into generic buckets. Don't build on top of these -- understand what the previous attempt did, rescue the files, and start fresh with your own taxonomy.
