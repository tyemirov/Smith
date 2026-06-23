#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "mutagen>=1.47",
#   "openpyxl>=3.1",
#   "Pillow>=10.0",
# ]
# ///
from __future__ import annotations

import base64
import csv
import json
import math
import shutil
import struct
import subprocess
import wave
import zipfile
import zlib
from html import escape
from pathlib import Path

import openpyxl
from mutagen.id3 import COMM, TALB, TIT2, TPE1, TXXX, ID3
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
FIXTURES_ROOT = ROOT / "fixtures"

PNG_PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO/aV9kAAAAASUVORK5CYII="
)


def reset_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_bytes(path: Path, data: bytes) -> None:
    ensure_parent(path)
    path.write_bytes(data)


def write_text(path: Path, text: str) -> None:
    ensure_parent(path)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_pdf(path: Path, *lines: str) -> None:
    ensure_parent(path)
    content_lines = []
    y = 760
    for index, line in enumerate(lines[:24]):
        size = 16 if index == 0 else 12
        content_lines.append(f"BT /F1 {size} Tf 72 {y} Td ({pdf_escape(line)}) Tj ET")
        y -= 22
    stream = "\n".join(content_lines).encode("latin-1", errors="ignore")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(bytes(pdf))


def write_docx(path: Path, *paragraphs: str) -> None:
    ensure_parent(path)
    body = []
    for paragraph in paragraphs:
        body.append(
            f"<w:p><w:r><w:t xml:space=\"preserve\">{escape(paragraph)}</w:t></w:r></w:p>"
        )
    document_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        "<w:body>"
        + "".join(body)
        + "<w:sectPr/></w:body></w:document>"
    )
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document_xml)


def write_zip(path: Path, members: dict[str, str | bytes]) -> None:
    ensure_parent(path)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def write_json(path: Path, payload: object) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[list[str]]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)


def write_xlsx(path: Path, rows: list[list[str]]) -> None:
    ensure_parent(path)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Data"
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def write_image(path: Path) -> None:
    write_bytes(path, PNG_PIXEL)


def touch(path: Path) -> None:
    ensure_parent(path)
    path.write_bytes(b"")


def write_ics(path: Path, *, summary: str, description: str, location: str = "") -> None:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "BEGIN:VEVENT",
        "UID:tidy-folder-fixture",
        "DTSTAMP:20260412T150000Z",
        "DTSTART:20260415T150000Z",
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{description}",
    ]
    if location:
        lines.append(f"LOCATION:{location}")
    lines.extend(["END:VEVENT", "END:VCALENDAR"])
    write_text(path, "\n".join(lines))


def best_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def write_ocr_image(path: Path, lines: list[str]) -> None:
    ensure_parent(path)
    width = 1400
    height = 300 + (len(lines) * 90)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = best_font(54)
    y = 60
    for line in lines:
        draw.text((70, y), line, fill="black", font=font)
        y += 90
    image.save(path)


def write_silent_mp3_with_tags(path: Path, *, title: str, artist: str, album: str, comment: str) -> None:
    ensure_parent(path)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        subprocess.run(
            [
                ffmpeg,
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=44100:cl=mono",
                "-t",
                "1",
                "-q:a",
                "9",
                str(path),
            ],
            check=True,
        )
    else:
        # Fallback: create a tiny silent WAV and rely on mutagen tags.
        wav_path = path.with_suffix(".wav")
        with wave.open(str(wav_path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(44100)
            samples = bytearray()
            for _ in range(44100):
                samples.extend(struct.pack("<h", 0))
            handle.writeframes(bytes(samples))
        wav_path.replace(path)

    tags = ID3()
    tags.add(TIT2(encoding=3, text=title))
    tags.add(TPE1(encoding=3, text=artist))
    tags.add(TALB(encoding=3, text=album))
    tags.add(TXXX(encoding=3, desc="workflow", text=comment))
    tags.add(COMM(encoding=3, lang="eng", desc="comment", text=comment))
    tags.save(path)


def build_freelance_designer() -> None:
    target = FIXTURES_ROOT / "freelance-designer" / "test-folder"
    reset_dir(target)

    pdf_files = {
        "invoice-acme-corp-march.pdf": [
            "Acme Corp Invoice March",
            "Client: Acme Corp",
            "Invoice total: 4500",
            "Project: Rebrand identity sprint",
        ],
        "invoice-acme-corp-april.pdf": [
            "Acme Corp Invoice April",
            "Client: Acme Corp",
            "Invoice total: 3200",
            "Project: Packaging revision",
        ],
        "alice-report-card-q2.pdf": [
            "Alice Report Card Q2",
            "Student: Alice",
            "School: Redwood Elementary",
            "Reading: Excellent",
            "Math: Strong progress",
        ],
        "peter-vaccination-record.pdf": [
            "Pediatric Vaccination Record",
            "Patient: Peter",
            "Immunization: MMR booster",
            "Clinic: Pine Pediatrics",
        ],
        "mortgage-statement-feb.pdf": [
            "Mortgage Statement February",
            "Loan servicer: Evergreen Home Loans",
            "Monthly balance summary",
        ],
        "tax-return-2024.pdf": [
            "Tax Return 2024",
            "IRS filing summary",
            "Freelance income and deductions",
        ],
        "1099-freelance-2024.pdf": [
            "Form 1099-NEC",
            "Freelance income from Acme Corp",
        ],
        "peter-math-worksheet.pdf": [
            "Math Worksheet",
            "Student: Peter",
            "School homework packet",
        ],
        "alice-art-class-schedule.pdf": [
            "Alice Art Class Schedule",
            "School enrichment calendar",
            "Art class pickup information",
        ],
        "pantone-color-guide.pdf": [
            "Pantone Color Guide",
            "Branding reference for client palette",
        ],
        "home-insurance-renewal.pdf": [
            "Home Insurance Renewal",
            "Home insurance coverage summary",
            "Property renewal date",
        ],
        "recipe-sourdough.pdf": [
            "Sourdough Recipe",
            "Ingredients and baking schedule",
        ],
        "Sorted/PDFs/manual.pdf": [
            "Dishwasher Manual",
            "Appliance installation and warranty guide",
        ],
    }
    for relative_path, lines in pdf_files.items():
        write_pdf(target / relative_path, *lines)

    write_docx(
        target / "client-brief-rebrand.docx",
        "Client brief for Acme rebrand.",
        "Deliverables: logo refresh, typography system, launch assets.",
        "Campaign owner: Acme Corp marketing team.",
    )
    write_csv(
        target / "quarterly-client-roster.csv",
        [
            ["client", "project", "status"],
            ["Acme Corp", "Rebrand", "Active"],
            ["Northwind", "Website refresh", "Paused"],
        ],
    )
    write_xlsx(
        target / "worksheet-data.xlsx",
        [
            ["client", "invoice", "status"],
            ["Acme Corp", "March branding invoice", "Paid"],
            ["Northwind", "Proposal revision", "Awaiting signature"],
        ],
    )
    write_zip(
        target / "dribbble-export.zip",
        {"preview.txt": "Dribbble export for logo exploration and branding reviews.\n"},
    )
    write_json(
        target / "figma-components.fig.meta.json",
        {"tool": "Figma", "library": "Marketing components", "owner": "Acme Corp"},
    )
    write_text(target / "Sorted/Documents/random-notes.txt", "Loose notes from a previous sorting attempt.")
    write_ics(
        target / "dentist-appointment.ics",
        summary="Doctor appointment with dentist",
        description="Doctor visit and cleaning appointment for family dental checkup.",
        location="Downtown Dental",
    )
    write_ics(
        target / "school-pickup-calendar.ics",
        summary="School pickup duty",
        description="School pickup schedule for Alice art class and Peter homework club.",
        location="Redwood Elementary",
    )
    write_silent_mp3_with_tags(
        target / "track01.mp3",
        title="Weekend Theme Track",
        artist="House Demo",
        album="AI Songs",
        comment="Made with Suno for family trip montage",
    )
    for relative_path in [
        "headshot-2024.jpg",
        "family-photo-xmas.heic",
        "IMG_4521.heic",
        "IMG_4522.heic",
        "IMG_4523.heic",
        "screenshot-2024-03-15.png",
        "screenshot-2024-03-18.png",
        "Sorted/Images/old-photo.jpg",
    ]:
        write_image(target / relative_path)
    for relative_path, payload in {
        "logo-draft-v3.psd": b"PSD placeholder",
        "logo-final.ai": b"AI placeholder",
        "figma-components.fig": b"FIG placeholder",
    }.items():
        write_bytes(target / relative_path, payload)


def build_polluted_project() -> None:
    target = FIXTURES_ROOT / "polluted-project" / "test-folder"
    reset_dir(target)

    for relative_path, content in {
        "README.md": "# Polluted Project\n\nPrototype web app for internal collaboration.\n",
        "src/index.ts": "export const appName = 'polluted-project';\n",
        "src/components/Header.tsx": "export function Header() { return <header>Dashboard</header>; }\n",
        "src/components/Footer.tsx": "export function Footer() { return <footer>Status</footer>; }\n",
        "src/utils/helpers.ts": "export const slugify = (value: string) => value.toLowerCase();\n",
        "dist/bundle.js": "console.log('compiled bundle');\n",
        ".gitignore": "node_modules/\ndist/\n",
    }.items():
        write_text(target / relative_path, content)

    write_json(
        target / "package.json",
        {
            "name": "polluted-project",
            "private": True,
            "scripts": {"build": "vite build", "dev": "vite"},
            "dependencies": {"react": "^18.0.0"},
        },
    )
    write_json(
        target / "package-lock.json",
        {
            "name": "polluted-project",
            "lockfileVersion": 3,
            "packages": {"": {"name": "polluted-project"}},
        },
    )
    write_json(
        target / "tsconfig.json",
        {
            "compilerOptions": {"target": "ES2022", "module": "ESNext", "jsx": "react-jsx"},
            "include": ["src"],
        },
    )
    write_docx(
        target / "meeting-notes-standup.docx",
        "Standup notes for the prototype web app React TypeScript codebase.",
        "Action items: fix auth flow in src/components/Header.tsx and clean uploads folder.",
        "Build blockers: update package.json scripts, verify tsconfig paths, and re-run vite build.",
    )
    write_pdf(
        target / "tax-2023.pdf",
        "Tax Summary 2023",
        "IRS filing receipt",
        "Personal tax document",
    )
    write_pdf(
        target / "download.pdf",
        "Downloaded conference schedule",
        "General agenda PDF with no clear project home.",
    )
    write_pdf(
        target / "download (1).pdf",
        "Downloaded vendor flyer",
        "Generic brochure with no clear home.",
    )
    write_pdf(
        target / "src/random-invoice.pdf",
        "Random Invoice",
        "Client invoice misplaced inside src folder",
    )
    write_text(target / "recipe-from-mom.txt", "Sourdough starter recipe from mom.\n")
    for relative_path in [
        "vacation-photo.heic",
        "screenshot 2024-01-15 at 3.45.12 PM.png",
        "src/components/cat-meme.jpg",
    ]:
        write_image(target / relative_path)
    touch(target / "IMG_0042.MOV")
    touch(target / "node_modules/.package-lock.json")
    touch(target / ".git/objects/pack")


def build_retiree_documents() -> None:
    target = FIXTURES_ROOT / "retiree-documents" / "test-folder"
    reset_dir(target)

    pdf_files = {
        "blood-test-results-2024.pdf": [
            "Blood Test Results 2024",
            "Lab result summary for annual physical",
        ],
        "blood-test-results-2023.pdf": [
            "Blood Test Results 2023",
            "Lab result summary for annual physical",
        ],
        "dr-smith-referral.pdf": [
            "Doctor Referral",
            "Referral from Dr. Smith to cardiology",
        ],
        "prescription-metformin.pdf": [
            "Prescription Metformin",
            "Medical refill instructions",
        ],
        "social-security-statement.pdf": [
            "Social Security Statement",
            "Retirement benefits estimate and pension overview",
        ],
        "401k-rollover-2020.pdf": [
            "401k Rollover 2020",
            "Retirement account transfer summary",
        ],
        "pension-statement-q4-2024.pdf": [
            "Pension Statement Q4 2024",
            "Retirement pension balance summary",
        ],
        "tax-return-2024.pdf": ["Tax Return 2024", "IRS filing summary"],
        "tax-return-2023.pdf": ["Tax Return 2023", "IRS filing summary"],
        "tax-return-2022.pdf": ["Tax Return 2022", "IRS filing summary"],
        "property-tax-2024.pdf": ["Property Tax 2024", "County property tax statement"],
        "home-deed.pdf": ["Home Deed", "Property deed record"],
        "will-and-testament-2022.pdf": ["Will and Testament", "Estate planning document"],
        "power-of-attorney.pdf": ["Power of Attorney", "Estate planning document"],
        "boeing-retirement-letter.pdf": ["Boeing Retirement Letter", "Retirement pension enrollment"],
        "patent-US7654321.pdf": ["Patent US7654321", "Engineering patent record"],
        "engineering-portfolio-2015.pdf": ["Engineering Portfolio", "Career portfolio and project history"],
        "cruise-tickets-alaska-2024.pdf": ["Cruise Tickets Alaska 2024", "Trip reservation and tickets"],
        "hotel-reservation-paris.pdf": ["Hotel Reservation Paris", "Travel reservation confirmation"],
        "woodworking-plans-bookshelf.pdf": ["Woodworking Plans", "Bookshelf hobby project measurements"],
        "garden-layout-2024.pdf": ["Garden Layout 2024", "Home garden plan and planting notes"],
        "hvac-maintenance-receipt.pdf": ["HVAC Maintenance Receipt", "Home maintenance service receipt"],
        "roof-inspection-2023.pdf": ["Roof Inspection 2023", "Home inspection report"],
        "car-title-toyota.pdf": ["Car Title Toyota", "Vehicle title document"],
        "auto-insurance-renewal.pdf": ["Auto Insurance Renewal", "Insurance policy summary"],
        "cookbook-scan-grandma.pdf": ["Grandma Cookbook Scan", "Family recipe collection"],
        "random-download.pdf": ["Downloaded flyer", "Generic brochure with no clear owner"],
    }
    for relative_path, lines in pdf_files.items():
        write_pdf(target / relative_path, *lines)

    write_docx(
        target / "Old Stuff/resume-1998.docx",
        "Resume 1998",
        "Senior engineer at Boeing.",
    )
    write_text(target / "Documents/notes.txt", "General notes from retirement planning meeting.")
    write_text(target / "Misc/unknown.dat", "opaque fixture payload")
    write_xlsx(
        target / "statement.xlsx",
        [
            ["account", "portfolio", "balance"],
            ["401k rollover", "Retirement portfolio", "245000"],
            ["Pension reserve", "Quarterly pension balance", "98000"],
        ],
    )
    write_ocr_image(
        target / "scan-001.png",
        [
            "PASSPORT SCAN",
            "TRAVEL DOCUMENT",
            "VISA PAGE",
        ],
    )
    for relative_path in [
        "medicare-card-scan.jpg",
        "passport-scan.jpg",
        "grandkids-birthday-2024.heic",
        "IMG_1234.jpg",
        "IMG_1235.jpg",
    ]:
        write_image(target / relative_path)
    touch(target / "grandkids-recital-video.mp4")


def build_all() -> None:
    build_freelance_designer()
    build_polluted_project()
    build_retiree_documents()


if __name__ == "__main__":
    build_all()
