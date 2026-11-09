"""Editorial withdrawal of unsupported publications; never rebuild run results.

An editorial notice has no gates, command, environment or CI run of its own.
Original files remain byte-for-byte in an archive and at their historical paths.
This module neither executes a recipe nor changes the historical report JSON.
"""
from __future__ import annotations

import hashlib
import html
import json
import pathlib
import re
import shutil

import publish_layout

LABEL = "Evidence insufficient"


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def notice(original: dict, review: dict) -> dict:
    reason = review["reason"]
    return {
        "schema": "strhub-verified/1", "record_type": "editorial_review",
        "mode": "publish", "tool": original["tool"], "source": original["source"],
        "instrument": original.get("instrument", "documented"),
        "generated": review["reviewed_at"], "ci_run": None,
        "scope": "Editorial evidence review; no new execution or finding about the tool.",
        "evidence_review": review,
        "verdict": {"code": "undetermined", "title": LABEL, "basis": "strhub", "reason": reason},
        "step1": {"code": "ours", "headline": LABEL, "body": reason,
                  "missing": [], "missing_text": []},
        "certificate": {
            "schema": "strhub-verified/certificate/1", "label": LABEL,
            "summary": {"result": LABEL, "why": reason,
                        "scope": "Editorial evidence review; no new execution."},
            "conclusion": [{"title": LABEL, "body": reason}],
        },
    }


def paragraphs(r: dict) -> list[tuple[str, str]]:
    review = r["evidence_review"]
    return [
        (LABEL, review["reason"]),
        ("Editorial correction, not a new verification",
         f"Prepared {review['reviewed_at']}. No tool was executed and no historical gate, "
         "command or log was rewritten. The former execution claim is withdrawn pending "
         "sufficient evidence. This is not a finding that the tool works or fails."),
        ("Preserved original publication", review["archive_url"]),
        ("Review record and file hashes", review["review_url"]),
        ("Recovered evidence", review["recovered_evidence_note"]),
    ]


def render_html(r: dict) -> str:
    esc = html.escape
    sections = []
    for title, body in paragraphs(r):
        text = (f'<a href="{esc(body, quote=True)}">Open preserved evidence</a>'
                if body.startswith("https://") else esc(body))
        sections.append(f"<h2>{esc(title)}</h2><p>{text}</p>")
    return ("<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{esc(r['tool']['name'])}: {LABEL}</title>"
            "<style>body{font:17px/1.6 system-ui;max-width:780px;margin:3rem auto;padding:0 1.5rem;"
            "color:#243340}h1{font-size:30px}h2{font-size:20px;margin-top:1.8rem}"
            "a{color:#006b78;overflow-wrap:anywhere}</style>"
            f"<h1>{esc(r['tool']['name'])}: publication under review</h1>"
            + "".join(sections) + "</html>\n")


def write_notice(folder: pathlib.Path, slug: str, r: dict) -> None:
    (folder / f"{slug}.json").write_text(json.dumps(r, indent=2) + "\n")
    (folder / f"{slug}.html").write_text(render_html(r))
    (folder / f"{slug}.summary.md").write_text(
        f"# {r['tool']['name']}: publication under review\n\n" +
        "\n\n".join(f"## {title}\n\n{body}" for title, body in paragraphs(r)) + "\n")
    (folder / f"{slug}.badge.json").write_text(json.dumps(
        {"schemaVersion": 1, "label": "STRhub Verified", "message": LABEL, "color": "lightgrey"}) + "\n")


def write_pdf_notice(path: pathlib.Path, r: dict) -> None:
    """A standalone editorial notice, never an execution certificate."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#006b78")
    styles["BodyText"].leading = 15
    story = [Paragraph(html.escape(r["tool"]["name"]) + ": publication under review", styles["Title"]),
             Spacer(1, 14)]
    for title, body in paragraphs(r):
        text = html.escape(body)
        if body.startswith("https://"):
            text = f'<link href="{html.escape(body, quote=True)}" color="#006b78">Open preserved evidence</link>'
        story += [Paragraph(html.escape(title), styles["Heading2"]),
                  Paragraph(text, styles["BodyText"]), Spacer(1, 8)]
    SimpleDocTemplate(str(path), pagesize=A4, rightMargin=50, leftMargin=50,
                      topMargin=48, bottomMargin=48,
                      title=r["tool"]["name"] + ": editorial evidence review").build(story)


def apply(site: pathlib.Path, slug: str, review: dict) -> dict:
    """Archive first, withdraw second. Caller renders the notice PDF separately.

    A fixed digest binds the review to the exact publication inspected. Existing
    archives are refused: corrections must use a new, identifiable revision.
    """
    if not re.fullmatch(r"[a-z0-9-]+", slug) or not re.fullmatch(r"[a-zA-Z0-9_-]+", review["id"]):
        raise ValueError("unsafe slug or review id")
    root = site / f"{slug}.json"
    if digest(root) != review["original_report_sha256"]:
        raise ValueError("publication changed since review; inspect it again")
    original = json.loads(root.read_text())
    sha = publish_layout.sha_of(original)
    if not sha or not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ValueError("publication has no pinned commit")
    historical = publish_layout.place_of(site, slug, sha, original["instrument"])
    if (historical / f"{slug}.json").read_bytes() != root.read_bytes():
        raise ValueError("alias differs from its historical report; inspect both first")
    archive = site / "evidence-reviews" / review["id"] / slug / "original"
    if archive.exists():
        raise ValueError("review archive already exists")
    files = publish_layout.report_files(site, slug) + sorted((site / slug).rglob("*"))
    files = [p for p in files if p.is_file()]
    if any(p.is_symlink() or not p.resolve().is_relative_to(site.resolve()) for p in files):
        raise ValueError("publication contains an unsafe path")
    inventory = {}
    for path in files:
        rel = path.relative_to(site)
        target = archive / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        inventory[str(rel)] = digest(target)
    review = {**review, "original_generated": original.get("generated"),
              "original_ci_run": original.get("ci_run"), "original_files_sha256": inventory}
    review_path = archive.parent / "review.json"
    review_path.write_text(json.dumps(review, indent=2) + "\n")
    publish_layout.retire(site, slug, sha, original["instrument"], review["reason"], review["reviewed_at"])
    # Preserve all old root files in the archive. A log or PDF from the former
    # report must not appear to be evidence belonging to this editorial notice.
    for path in publish_layout.report_files(site, slug):
        path.unlink()
    r = notice(original, review)
    write_notice(site, slug, r)
    return r
