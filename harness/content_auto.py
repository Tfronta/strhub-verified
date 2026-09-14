"""Does the output have the shape of genotyping data, without being told where to look?

The Content gate used to need the manifest to say which column is the locus,
which is the sequence and which are the counts. A recipe proposed from a
repository has no one to say that, so every trial stopped at "Expected IO".
This works it out from the output itself, per format, and from what the run
was GIVEN: the regions file and the dataset's panel name the loci a genotype
call can be about, and a call that is about one of them is the evidence.

Two readers, same question, same answer shape as the manifest-driven analysis
(so reports, the index and the web keep working):

  VCF     records with CHROM/POS/REF/ALT and a sample column; a call is a
          record whose GT is not missing; a locus is recognised when the
          record's ID or its position lands on one of the regions given.
  table   TSV/CSV/text: the column whose values look like forensic locus
          names is the locus column; a column of ACGTN strings is sequence;
          integer columns are counts. Counts and sequence are welcome, not
          required: some tools write only alleles.

What this does NOT do: judge whether any genotype is right. A record with a
called allele at TH01 is evidence the tool produced its documented kind of
output; whether the allele is 9.3 or 6 is concordance, out of scope.
"""
from __future__ import annotations

import collections
import csv
import gzip
import pathlib
import re

#: Names a forensic STR/SNP locus can carry, for tables that name them.
LOCUS_RE = re.compile(
    r"^(?:D\d{1,2}S\d{2,5}|DY[SF]\d{2,4}[a-z]?(?:[./_-]?[12ab])?|Y[-_ ]?GATA[-_ ]?[A-Z]\d{0,2}|"
    r"DXS\d{3,5}|TH01|TPOX|CSF1PO|FGA|vWA|VWA|SE33|Penta[ _]?[DE]|PentaD|PentaE|AMEL(?:OGENIN)?[XY]?|"
    r"D\d{1,2}S\d{2,5}[._][12]|rs\d{3,}|[A-Z]{2,6}\d{0,3}[-_]?(?:STR)?)$", re.I)
#: The generic tail of LOCUS_RE ([A-Z]{2,6}\d...) is loose on purpose for names
#: like HTT or ATXN3; a column counts as the locus column only when most of its
#: values match AND at least a few are unmistakably forensic (the strict set).
STRICT_LOCUS_RE = re.compile(
    r"^(?:D\d{1,2}S\d{2,5}(?:[._][12])?|DY[SF]\d{2,4}[a-z]?(?:[./_-]?[12ab])?|Y[-_ ]?GATA[-_ ]?[A-Z]\d{0,2}|"
    r"DXS\d{3,5}|TH01|TPOX|CSF1PO|FGA|vWA|VWA|SE33|Penta[ _]?[DE]|PentaD|PentaE|AMEL(?:OGENIN)?[XY]?|rs\d{3,})$", re.I)
DNA_RE = re.compile(r"^[ACGTN]{4,}$", re.I)
INT_RE = re.compile(r"^\d+$")
ALLELE_RE = re.compile(r"^\d{1,2}(?:\.\d)?$")
#: How far a VCF POS may sit from a region's start and still be that region's
#: call. Tools anchor a repeat a few bases apart; 50 bp covers every one seen.
POS_SLACK = 50


def _read_text(path: pathlib.Path) -> str:
    if path.name.endswith(".gz"):
        return gzip.open(path, "rt", errors="replace").read()
    return path.read_text(errors="replace")


def read_regions(path: pathlib.Path | None) -> list[tuple[str, int, int, str]]:
    """(chrom, start, end, name) from any BED-like regions file (name = col 4
    when it is not numeric, else the 6th column for HipSTR, else chrom:start)."""
    if not path or not path.is_file():
        return []
    out = []
    for ln in path.read_text(errors="replace").splitlines():
        s = ln.strip()
        if not s or s.startswith(("#", "track", "browser")):
            continue
        f = s.split("\t") if "\t" in s else s.split()
        if len(f) < 3 or not INT_RE.match(f[1]) or not INT_RE.match(f[2]):
            continue
        name = ""
        for i in (5, 3):
            if len(f) > i and not INT_RE.match(f[i]) and not re.match(r"^\d+(\.\d+)?$", f[i]) \
                    and not re.match(r"^[ACGTN]+$", f[i], re.I):
                name = f[i]
                break
        out.append((f[0], int(f[1]), int(f[2]), name or f"{f[0]}:{f[1]}"))
    return out


def name_regions(regions, panel_path: pathlib.Path | None):
    """Give nameless regions (GangSTR's 5-column layout has none) the panel's
    names, by overlap, so the report can say TH01 rather than chr11:2171088."""
    panel = read_regions(panel_path) if panel_path else []
    if not panel or all(not r[3].startswith(r[0] + ":") for r in regions):
        return regions
    named = []
    for chrom, start, end, name in regions:
        if name.startswith(chrom + ":"):
            for pc, ps, pe, pn in panel:
                if pc == chrom and ps <= start and end <= pe:
                    name = pn
                    break
        named.append((chrom, start, end, name))
    return named


def _empty_stats() -> dict:
    return {"rows": 0, "header_row_dropped": False, "malformed_rows": 0, "dna_invalid_rows": 0,
            "count_invalid_rows": 0, "distinct_loci": 0, "distinct_str_loci": 0,
            "distinct_snp_markers": 0, "loci": [], "str_loci": [], "snp_markers": [],
            "total_reads": 0, "max_sequence_depth": 0, "top_loci_by_depth": []}


def analyze_vcf(path: pathlib.Path, regions: list[tuple[str, int, int, str]]) -> dict:
    """VCF records, called genotypes, and which of the given regions they land on."""
    rows = 0
    called = 0
    bad = 0
    depth_total = 0
    max_depth = 0
    hits: dict[str, int] = collections.OrderedDict()
    hit_depth: collections.Counter = collections.Counter()
    by_chrom: dict[str, list[tuple[int, int, str]]] = collections.defaultdict(list)
    for chrom, start, end, name in regions:
        by_chrom[chrom].append((start, end, name))
        by_chrom[chrom.removeprefix("chr")].append((start, end, name))
    names = {n for _, _, _, n in regions}

    for ln in _read_text(path).splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        f = ln.rstrip("\n").split("\t")
        if len(f) < 8:
            bad += 1
            continue
        rows += 1
        chrom, pos, vid, ref = f[0], f[1], f[2], f[3]
        if not INT_RE.match(pos) or not DNA_RE.match(ref) and not re.match(r"^[ACGTN]+$", ref, re.I):
            bad += 1
        depth = 0
        gt_called = False
        if len(f) >= 10 and f[8]:
            fmt = f[8].split(":")
            sample = f[9].split(":")
            if "GT" in fmt:
                gi = fmt.index("GT")
                gt = sample[gi] if gi < len(sample) else "."
                gt_called = bool(gt) and gt not in (".", "./.", ".|.")
            if "DP" in fmt:
                di = fmt.index("DP")
                try:
                    depth = int(sample[di]) if di < len(sample) else 0
                except ValueError:
                    depth = 0
        if gt_called:
            called += 1
        depth_total += depth
        max_depth = max(max_depth, depth)
        # Which given locus is this record about: its ID when the tool writes
        # the name there (HipSTR does), else the region its position lands on.
        locus = vid if vid in names else None
        if locus is None and INT_RE.match(pos):
            p = int(pos)
            for start, end, name in by_chrom.get(chrom, []):
                if start - POS_SLACK <= p <= end + POS_SLACK:
                    locus = name
                    break
        if locus is None and vid not in (".", ""):
            locus = vid
        if locus:
            hits[locus] = hits.get(locus, 0) + 1
            hit_depth[locus] += depth

    snp = sorted(l for l in hits if re.match(r"^rs\d+$", l, re.I))
    strs = sorted(l for l in hits if l not in snp)
    stats = _empty_stats()
    stats.update({
        "rows": rows, "malformed_rows": bad, "called_genotypes": called,
        "distinct_loci": len(hits), "distinct_str_loci": len(strs), "distinct_snp_markers": len(snp),
        "loci": strs + snp, "str_loci": strs, "snp_markers": snp,
        "regions_given": len(regions), "regions_hit": sum(1 for n in names if n in hits) if names else len(hits),
        "total_reads": depth_total, "max_sequence_depth": max_depth,
        "top_loci_by_depth": hit_depth.most_common(),
    })
    return stats


def analyze_table(path: pathlib.Path, fmt: str, panel_names: set[str] | None = None) -> dict:
    """Find the locus column (and sequence / count columns) of a table by what
    its values look like, then count what the manifest-driven analysis counts."""
    text = _read_text(path)
    delim = "\t" if fmt in ("tsv", "text") else ","
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    if fmt == "text" and lines and "\t" not in lines[0] and "," in lines[0]:
        delim = ","
    rows = [r for r in csv.reader(lines, delimiter=delim) if any(c.strip() for c in r)]
    stats = _empty_stats()
    if not rows:
        return stats
    width = collections.Counter(len(r) for r in rows).most_common(1)[0][0]
    body = [r for r in rows if len(r) == width]
    panel = {n.lower() for n in (panel_names or set())}

    def col(i):
        return [r[i].strip() for r in body]

    def locus_score(vals):
        if not vals:
            return 0.0
        loose = sum(1 for v in vals if LOCUS_RE.match(v.split(":")[0]))
        strict = sum(1 for v in vals if STRICT_LOCUS_RE.match(v.split(":")[0]) or v.split(":")[0].lower() in panel)
        if strict < 3 and not (panel and strict >= 1):
            return 0.0
        return loose / len(vals)

    scores = [(locus_score(col(i)), i) for i in range(width)]
    best_score, locus_col = max(scores)
    # Header: the first row is a header when it does not look like data in the
    # locus column but the rest does.
    header_dropped = False
    if len(body) > 1 and best_score > 0:
        first = body[0][locus_col].strip().split(":")[0]
        rest = [r[locus_col].strip().split(":")[0] for r in body[1:]]
        def strict(v):
            return bool(STRICT_LOCUS_RE.match(v)) or v.lower() in panel
        # "Locus", "Marker", "Name" pass the loose pattern; what marks a header
        # is the first row NOT being an unmistakable locus while the rows below
        # mostly are, or any other column of the first row being non-numeric
        # over a numeric column.
        numeric_cols = [i for i in range(width) if i != locus_col
                        and sum(1 for r in body[1:] if INT_RE.match(r[i].strip()) or ALLELE_RE.match(r[i].strip())) >= 0.8 * len(rest)]
        first_row_labels = any(not (INT_RE.match(body[0][i].strip()) or ALLELE_RE.match(body[0][i].strip())) for i in numeric_cols)
        if (not strict(first) and sum(1 for v in rest if strict(v)) >= 0.5 * len(rest)) or first_row_labels:
            body = body[1:]
            header_dropped = True
    if best_score < 0.5:
        stats.update({"rows": len(body), "header_row_dropped": header_dropped, "locus_column_found": False})
        return stats

    dna_cols = [i for i in range(width) if i != locus_col and sum(1 for v in col(i) if DNA_RE.match(v)) >= 0.8 * len(body)]
    # A column of small numbers with an occasional .3 is alleles (6, 9.3, 12);
    # a column of larger integers is reads. Alleles are decided first, so a
    # profile table is not read as counts.
    allele_cols = [i for i in range(width) if i != locus_col
                   and sum(1 for v in col(i) if ALLELE_RE.match(v)) >= 0.8 * len(body)
                   and max((float(v) for v in col(i) if ALLELE_RE.match(v)), default=0) <= 60]
    int_cols = [i for i in range(width) if i != locus_col and i not in allele_cols
                and sum(1 for v in col(i) if INT_RE.match(v)) >= 0.8 * len(body)]
    locus_rows: collections.Counter = collections.Counter()
    locus_reads: collections.Counter = collections.Counter()
    total = 0
    max_depth = 0
    for r in body:
        locus = r[locus_col].strip().split(":")[0]
        depth = 0
        for i in int_cols:
            try:
                depth += int(r[i])
            except ValueError:
                pass
        locus_rows[locus] += 1
        locus_reads[locus] += depth
        total += depth
        max_depth = max(max_depth, depth)
    snp = sorted(l for l in locus_rows if re.match(r"^rs\d+$", l, re.I))
    strs = sorted(l for l in locus_rows if l not in snp)
    stats.update({
        "rows": len(body), "header_row_dropped": header_dropped, "locus_column_found": True,
        "locus_column": locus_col, "dna_columns": dna_cols, "count_columns": int_cols, "allele_columns": allele_cols,
        "distinct_loci": len(locus_rows), "distinct_str_loci": len(strs), "distinct_snp_markers": len(snp),
        "loci": strs + snp, "str_loci": strs, "snp_markers": snp,
        "total_reads": total, "max_sequence_depth": max_depth, "top_loci_by_depth": locus_reads.most_common(),
    })
    if panel:
        stats["panel_loci_present"] = sorted(l for l in locus_rows if l.lower() in panel)
    return stats


def judge(stats: dict, fmt: str, regions_given: int) -> dict:
    """The checks the auto analysis stands on. Conservative and stated:
    records exist, genotypes were called (VCF), and enough of the loci the run
    was given came back (or, with nothing given, enough recognisable loci)."""
    checks: dict = {"records_present": stats.get("rows", 0) > 0}
    if fmt == "vcf":
        called = stats.get("called_genotypes", 0)
        checks["genotypes_called"] = called > 0 and called >= 0.5 * max(stats.get("rows", 0), 1)
        if regions_given:
            need = max(3, int(0.3 * regions_given))
            checks["given_loci_recognised"] = stats.get("regions_hit", 0) >= need
        else:
            checks["loci_recognised"] = stats.get("distinct_loci", 0) >= 3
    else:
        checks["locus_column_found"] = bool(stats.get("locus_column_found"))
        checks["loci_recognised"] = stats.get("distinct_loci", 0) >= 3
        checks["calls_or_counts_present"] = bool(stats.get("count_columns") or stats.get("dna_columns")
                                                  or stats.get("allele_columns"))
    return checks
