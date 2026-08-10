"""Write a rejection notice for a run that was stopped before it could be judged.

A stopped run still owes the submitter an explanation, and the explanation is
useless — worse than useless — unless it says WHOSE fault it is.

Two things can stop a run before the gates, and they belong to opposite parties:

  author  the BED targets coordinates the reference slice does not cover, or is
          malformed. The submission is wrong; the tool is untested, not failed.
          Fixing it is free and the author is the only one who can.

  strhub  the manifest names a regions BED that is not in this repo. The author's
          BED passed validation at submit time, so its absence here is ours. An
          author told to "check the path" in this case would go edit a file that
          was already correct.

Both used to surface the same way, or not at all. A missing BED left the
pre-flight SKIPPED rather than failed (it is conditioned on a BED being staged),
so the run continued without one, the tool targeted nothing, and it earned an
`installs` badge with a diagnostics line reading "corrections to the submission".
That sentence was addressed to the wrong person.

The notice deliberately does NOT go to `reports/`: that directory is the public
attestation, and a stopped run has nothing to attest. It goes to
`state/rejections/<slug>.json`, which the web side reads to tell the submitter
what happened.

Usage:
  python harness/rejection.py --tool <slug> --fault strhub --reason regions_not_staged \
      --detail "tools/<slug>/assets/regions.bed" --run-url <url>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "state" / "rejections"

# Per reason: who it belongs to, what the submitter is told, and what to do next.
# Keeping the copy here rather than in the workflow keeps the two callers from
# drifting into two different explanations of the same failure.
REASONS: dict[str, dict[str, str]] = {
    "regions_not_staged": {
        "fault": "strhub",
        "title": "The regions BED named by the manifest was not present in the engine repo",
        "next_step": (
            "Nothing to fix on your side. Your BED was validated against the "
            "supported-loci panel when you submitted it, so this is a fault in "
            "STRhub's submission pipeline, not in your tool or your BED. "
            "Re-submitting the form re-uploads it and the run will proceed."
        ),
    },
    "regions_outside_panel": {
        "fault": "author",
        "title": "The regions BED targets coordinates the reference slice does not cover",
        "next_step": (
            "STRhub's reference BAM is a slice over forensic STR loci, not a whole "
            "genome, so a tool aimed outside it would find no reads and look broken "
            "through no fault of its own. Download the supported-loci panel for your "
            "input type and rebuild your BED within those windows, then re-submit. "
            "Re-verification is free."
        ),
    },
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", required=True)
    ap.add_argument("--reason", required=True, choices=sorted(REASONS))
    ap.add_argument("--detail", default="", help="Path or message naming the specific item")
    ap.add_argument("--validation", help="regions_validation.json from validate_bed.py")
    ap.add_argument("--run-url", default="")
    args = ap.parse_args()

    spec = REASONS[args.reason]
    notice = {
        "schema": "strhub-verified/rejection/1",
        "slug": args.tool,
        # The whole point of the file. A consumer that ignores this field and
        # renders the text anyway is back to blaming the author for our bugs.
        "fault": spec["fault"],
        "reason": args.reason,
        "title": spec["title"],
        "detail": args.detail,
        "next_step": spec["next_step"],
        "gates_run": False,
        "run_url": args.run_url,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }

    # The validator's own reasons are more specific than anything this file can
    # say generically, so carry them through verbatim when we have them.
    if args.validation:
        try:
            notice["validation"] = json.loads(pathlib.Path(args.validation).read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"::warning::could not read {args.validation}: {exc}", file=sys.stderr)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / f"{args.tool}.json"
    dest.write_text(json.dumps(notice, indent=2) + "\n")

    print(f"::notice::rejection ({spec['fault']}): {spec['title']}")
    print(json.dumps(notice, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
