"""The claims register: every sentence the engine asserts about somebody else's
software, and what each one rests on.

Why this file exists. A report published under STRhub's name says things about
a stranger's work, and a heuristic that produces a number is not entitled to
speak in the author's voice. STRhub reported that STRspy's README "suggests
ont-fastq first" — a keyword count, 7 mentions against 4, about a README that
documents both inputs and recommends BAM outright. It reached a published page
and was caught by a reader who happened to know the tool, which is the one
reader the system is not built for. A second one had been in every certificate
since June: "This tool does not include its own demo or test data", printed
whatever the repository held, false for STRsearch and its 35 example files.

What is registered. Every string in the report-generating modules that speaks
in FINDING voice — that asserts something about the tool, its repository, its
documentation or its author. Observations about STRhub's own run are not
findings and are not registered.

What the sources mean:

  tree          the repository's file list, read at the pinned ref
  readme        text read from the README at the pinned ref
  log           a line the tool itself printed, captured with its matches
  manifest      something the submission declared
  gates         the outcome of this run's own gates
  run           STRhub's own configuration or choice for this run
  strhub-table  STRhub's own knowledge (e.g. which BED layout a tool reads).
                Legitimate, but it is OUR claim: the sentence must not imply
                the author said it.
  policy        a statement about STRhub's scope, not about the tool
  advice        an instruction to the reader, asserting nothing

How to use it. Change or add a finding sentence and the test fails with its
fingerprint: register it with the source it rests on. That is the review — a
sentence nobody can source is a sentence nobody should publish. See
harness/tests/test_claims_have_evidence.py and
docs/PLAN-Claims-Need-Evidence.md.
"""
from __future__ import annotations

#: fingerprint -> (module, evidence source). The fingerprint is sha256[:12] of
#: the whitespace-normalised string, so moving code does not invalidate it and
#: rewording does.
REGISTER: dict[str, tuple[str, str]] = {
    "4800fd91183e": ("certificate_text", "tree"),  # The repository ships example data (
    "3badef4c3d59": ("certificate_text", "tree"),  # ships no test or demo data of its own.
    "33eed44a270b": ("diagnose_log", "log"),  # A COPY/ADD line names a file the build cannot see. The container is built from the tool's direc
    "86baeea971be": ("diagnose_log", "run"),  # At least one cause is STRhub's, not the tool's: the container recipe for a generated environmen
    "c607109d1c34": ("diagnose_log", "manifest"),  # Every cause identified sits in what the submission declared — its pinned versions, package name
    "f87ad4ad59ea": ("diagnose_log", "manifest"),  # The tool declares a binary or proprietary output with no text or tabular export, so the IO and 
    "6759a67a2817": ("diagnose_log", "manifest"),  # The tool declares an interactive or graphical step. The automated runner is headless and cannot
    "e3a029af91e7": ("diagnose_log", "manifest"),  # The tool declares it fetches data over the network while running. A pinned snapshot cannot reco
    "4b6b45793ca4": ("diagnose_log", "manifest"),  # The tool declares it needs GPU hardware. Public CI runners are CPU-only.
    "b1468dcdb3d3": ("diagnose_log", "manifest"),  # The tool declares it needs an OS the automated runner does not provide.
    "fb768926c8c4": ("diagnose_log", "manifest"),  # The tool declares it needs licensed or restricted reference data that cannot be published in a 
    "042eb41b7ca6": ("diagnose_log", "log"),  # The tool expected a file at '{0}' but it was not staged. Check the manifest inputs, fixture pat
    "f7faa0cc2ec7": ("diagnose_log", "log"),  # The tool needs CUDA hardware. Public CI runners are CPU-only, so this cannot run on the automat
    "94e9a73cf514": ("diagnose_log", "manifest"),  # The tool needs CUDA hardware. Public CI runners are CPU-only.
    "3d053d897ca4": ("diagnose_log", "manifest"),  # The tool needs a license or licensed data that cannot be published in a public verification run
    "92129cab0cf3": ("diagnose_log", "log"),  # The tool needs a license or licensed reference data that cannot be published in a public verifi
    "65d555ab9fba": ("diagnose_log", "manifest"),  # These are corrections to the CONFIGURATION this run used, which a third party supplied — not th
    "997283df285e": ("diagnose_log", "log"),  # This tool requires the VCF output path to end in .gz (bgzipped). Change the output path in the 
    "dc6dbb4a5df8": ("generate_pdf", "tree"),  # Recorded automatically from the tool's public files when this run was configured. Not verified 
    "6b4450723321": ("generate_pdf", "tree"),  # This tool ships no demo or test data of its own. STRhub ran the verification using the public r
    "c7c9908816cf": ("generate_pdf", "manifest"),  # This tool was submitted for verification by somebody other than its maintainer. The maintainer 
    "7ceb34632e90": ("propose_manifest", "tree"),  # # No install method was detected; a bare image so the trial can report # the documentation gap 
    "831100e24df2": ("propose_manifest", "tree"),  # # The repository ships its own Dockerfile (
    "ec6b7b9d5fd5": ("propose_manifest", "readme"),  # ' the README installs; its version is the package's, not necessarily the pinned commit.
    "18f4fe0bc984": ("propose_manifest", "strhub-table"),  # (no known format for this tool; plain chrom/start/end/name was tried).
    "3bc2e96f4a72": ("propose_manifest", "strhub-table"),  # (the tool is known to read this format).
    "0e6a6c086e9c": ("propose_manifest", "run"),  # , for which STRhub holds no reference sample; which input the tool is best used with is the aut
    "36152cfaf0d6": ("propose_manifest", "readme"),  # Run command: the README's own command, rewritten to STRhub's mounts; everything it created was 
    "714329de2505": ("propose_manifest", "readme"),  # the README points at; the tool inside it is whatever that image holds, not necessarily the pinn
    "70be7a8f1331": ("propose_manifest", "readme"),  # true # no command found in the README; nothing to run
    "2653eed3e17b": ("report", "policy"),  # <br><br> This is <b>not</b> a claim that the genotypes are correct, nor that the tool is fit fo
    "82688741465a": ("report", "manifest"),  # A container environment, built from the tool's declared install steps rather than from a recipe
    "316572e47dc0": ("report", "tree"),  # Recorded automatically from the tool's public files when this run was configured. **Not verifie
    "0bee1f1f9159": ("report", "run"),  # Test data: no sample from the repository was used, so a public reference sample stood in.
    "8abb5c27a292": ("report", "policy"),  # This is **not** a claim that the genotypes are correct, nor that the tool is fit for casework o
    "1d5d51eb4ad0": ("report", "manifest"),  # This tool was submitted for verification by somebody other than its maintainer. The maintainer 
    "36231f28bb59": ("report", "readme"),  # What the README does not say:
    "f48849517921": ("verdict", "readme"),  # No command line invoking the tool was found in the README.
    "dc452ca7ae85": ("verdict", "tree"),  # No way to install the tool was found: no Dockerfile, environment file, requirements, setup scri
    "6fbca0b9cb26": ("verdict", "run"),  # STRhub Verified could not run the tool: it holds no public reference sample of the input type t
    "570d333e2c0e": ("verdict", "gates"),  # STRhub Verified installed the tool from a clean checkout at the pinned commit and ran the comma
    "e134d3bb2a39": ("verdict", "gates"),  # STRhub Verified ran the tool to completion in a clean environment, but no output file in the do
    "03e9ebca6ee3": ("verdict", "gates"),  # STRhub Verified tried to run the tool in a clean environment on a public hg38 reference sample,
    "f3ce2c9fe046": ("verdict", "readme"),  # STRhub could not work out how to install or run this tool from its repository. The README does 
    "936deb76fffd": ("verdict", "run"),  # STRhub has no reference sample of the kind this tool reads, and the repository ships no example
    "ae2a210ac6f3": ("verdict", "run"),  # STRhub holds no reference sample of the kind this tool reads and the repository ships no exampl
    "78de22b7f559": ("verdict", "advice"),  # Say how the tool is installed and try again.
    "8c8f9a70b520": ("verdict", "strhub-table"),  # The tool needs a regions file (BED) in its own format. STRhub has ready-made files for the HipS
    "4b044277e315": ("verdict", "manifest"),  # The tool needs something the automated runner cannot provide:
    "3855d69d6067": ("verdict", "gates"),  # The tool ran to completion but produced no output file in the documented format.
    "768d4670e6ef": ("verdict", "gates"),  # The tool was installed but exited with an error when run.
    "9b7293a29fdb": ("verdict", "gates"),  # The tool's run produced its documented output, on the published environment the README points a
    "f84cc76d0787": ("verdict", "readme"),  # no command line invoking the tool was found in the README
    "e32acfe17c39": ("verdict", "tree"),  # no install method was found in the repository
    "0a4be5144c5f": ("verdict", "strhub-table"),  # the tool needs a regions file and STRhub does not know its format; a plain chrom/start/end/name
    "1dfe6b92d49e": ("verdict", "strhub-table"),  # the tool needs a regions file in its own format, which STRhub does not yet generate for it
}

#: Phrasings that may never be published, whatever evidence is attached: they
#: put a preference or an absence in the author's mouth, which no reading of a
#: repository establishes. The first two are the exact sentences that shipped.
FORBIDDEN = [
    (r"the README suggests", "a keyword count is not a reading; say which data this run used"),
    (r"(?:this |the )tool does not include its own",
     "absence needs evidence from the tree; see certificate_text.test_data_item"),
    (r"the (?:tool|author) prefers", "a preference is the author's to state, not ours to infer"),
    (r"the README (?:recommends|wants|expects)\b",
     "quote the line instead, or describe what STRhub did"),
    (r"is (?:designed|intended) (?:for|to)", "intent cannot be read off a repository"),
]

VALID_SOURCES = {"tree", "readme", "log", "manifest", "gates", "run",
                 "strhub-table", "policy", "advice"}
