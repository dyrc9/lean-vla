#!/usr/bin/env python3
"""Run the local NDSS 2027 manuscript submission preflight.

This checks the paper and its executable claim evidence.  It deliberately does
not build or package the anonymous experiment artifact.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = ROOT / "docs/paper/overleaf"
MAIN = PAPER_ROOT / "paper_ndss.tex"
PDF = PAPER_ROOT / "build/paper_ndss.pdf"
LOG = PAPER_ROOT / "build/paper_ndss.log"
ABSTRACT = PAPER_ROOT / "sections/abstract.tex"
INTRODUCTION = PAPER_ROOT / "sections/1-introduction.tex"
EVALUATION = PAPER_ROOT / "sections/6-evaluation.tex"
CONCLUSION = PAPER_ROOT / "sections/conclusion.tex"
DISCLOSURE = PAPER_ROOT / "sections/ai_disclosure.tex"
SUBMISSION_METADATA = ROOT / "docs/paper/ndss2027_submission_metadata.md"
DESIGN = PAPER_ROOT / "sections/4-design.tex"
IMPLEMENTATION = PAPER_ROOT / "sections/5-implementation.tex"
ETHICS = PAPER_ROOT / "sections/ethics.tex"

NEGATIVE_TESTS = (
    "tests/test_integrity_v4_runtime.py",
    "tests/test_l2_online_arm_runtime.py",
    "tests/test_integrity_prototype.py",
    "tests/test_recovery_runtime_v12.py",
    "tests/test_semantic_online_runner.py",
)


def run_checked(label: str, command: list[str], *, cwd: Path) -> str:
    executable = shutil.which(command[0])
    if executable is None:
        raise AssertionError(f"{label}: required executable not found: {command[0]}")
    command[0] = executable
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        tail = "\n".join(completed.stdout.splitlines()[-80:])
        raise AssertionError(
            f"{label}: command failed with exit {completed.returncode}\n{tail}"
        )
    print(f"PASS  {label}")
    return completed.stdout


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def require_tokens(label: str, text: str, tokens: tuple[str, ...]) -> None:
    missing = [token for token in tokens if token not in text]
    require(not missing, f"{label} drifted or is incomplete: {missing}")


def find_poppler_tool(name: str) -> str:
    executable = shutil.which(name)
    if executable is not None:
        return executable

    # The Codex document runtime exposes pdfinfo through a small wrapper while
    # keeping the rest of Poppler in its native dependency tree.  Derive that
    # tree without baking a user- or machine-specific absolute path into the
    # repository.  Ordinary environments take the PATH branch above.
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo is not None:
        dependency_root = Path(pdfinfo).resolve().parents[2]
        for relative in (
            f"native/poppler/poppler/bin/{name}",
            f"native/poppler/bin/{name}",
        ):
            candidate = dependency_root / relative
            if candidate.is_file():
                return str(candidate)
    raise AssertionError(f"PDF audit: required executable not found: {name}")


def find_pdffonts() -> str:
    return find_poppler_tool("pdffonts")


def validate_source_structure() -> list[str]:
    main = MAIN.read_text(encoding="utf-8")
    require("\\author{}" in main, "anonymous submission must keep \\author{}")
    require("\\pagestyle{plain}" in main, "submission must retain page numbers")
    ordered = (
        "\\input{sections/conclusion}",
        "\\input{sections/ai_disclosure}",
        "\\input{sections/ethics}",
        "\\bibliographystyle{IEEEtran}",
    )
    positions = [main.find(token) for token in ordered]
    require(all(position >= 0 for position in positions), "required paper sections missing")
    require(positions == sorted(positions), "conclusion/disclosure/ethics/references order drifted")

    manifest = (PAPER_ROOT / "sync_manifest.txt").read_text(encoding="utf-8")
    tex_sources = []
    for relative in (line.strip() for line in manifest.splitlines()):
        if relative.endswith(".tex"):
            tex_sources.append((PAPER_ROOT / relative).read_text(encoding="utf-8"))
    joined = "\n".join(tex_sources)
    require("/Users/" not in joined, "absolute user path found in synchronized TeX")
    require(
        re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}", joined, re.I) is None,
        "email address found in synchronized TeX",
    )

    pending = []
    if "24xxxx" in main:
        pending.append("replace DOI paper-number placeholder 24xxxx")
    disclosure = re.sub(r"\s+", " ", DISCLOSURE.read_text(encoding="utf-8"))
    require(
        "LaTeX/TikZ diagrams" in disclosure,
        "Generative-AI disclosure must cover diagram preparation",
    )
    require(
        "reviewed the generated material" in disclosure,
        "Generative-AI disclosure must retain author-review responsibility",
    )
    require(
        "all manuscript sections" in disclosure
        and "Figs.~2--3" in disclosure
        and "raster artwork for Figs.~1 and~4" in disclosure,
        "Generative-AI disclosure must identify the generated prose/figure scope",
    )
    design = re.sub(r"\s+", " ", DESIGN.read_text(encoding="utf-8"))
    implementation = re.sub(
        r"\s+", " ", IMPLEMENTATION.read_text(encoding="utf-8")
    )
    require_tokens(
        "two-stage design structure",
        design,
        (
            "two alignment stages and three components",
            "L1 Intent-to-ActionBlock Assessment",
            "L2 ActionBlock-to-Execution Alignment",
            "L2a Transaction Binding",
            "L2b State-Conditioned Guard Screening",
            "Its contract states which evidence must be observed",
            "Triggered guard screening occurs before the corresponding dispatch",
            "Receipts and effects then close the transaction",
        ),
    )
    require_tokens(
        "implementation component structure",
        implementation,
        (
            "The \\lone component derives a task graph",
            "The \\ltwoa component holds the current proposal",
            "The \\ltwob component snapshots simulator and controller state",
            "before real dispatch",
            "source-action identity is encoded as schema-tagged",
            "whitespace-free UTF-8 JSON over finite Python-float values",
            "array dtype or endianness",
        ),
    )
    require(
        "sole environment-step interface" in implementation
        and "complete mediation assumes" in implementation,
        "reference-monitor prose must retain the complete-mediation assumption",
    )
    require(
        "fresh nonce" not in design
        and "A fresh permission names the proposal" in design
        and "can open exactly one transaction" in design,
        "design must retain a fresh, one-use proposal permission",
    )
    ethics = re.sub(r"\s+", " ", ETHICS.read_text(encoding="utf-8"))
    require(
        "The study is simulator-only" in ethics
        and "every attack, benchmark agent, and contact" in ethics
        and "is synthetic" in ethics,
        "ethics statement must disambiguate the simulated human_safety suite",
    )

    abstract = re.sub(r"\s+", " ", ABSTRACT.read_text(encoding="utf-8"))
    introduction = re.sub(
        r"\s+", " ", INTRODUCTION.read_text(encoding="utf-8")
    )
    evaluation = re.sub(r"\s+", " ", EVALUATION.read_text(encoding="utf-8"))
    conclusion = re.sub(r"\s+", " ", CONCLUSION.read_text(encoding="utf-8"))
    require_tokens(
        "abstract evidence summary",
        abstract,
        (
            "intent--action authorization gap",
            "action--execution realization gap",
            "establishes a scoped alignment chain across the two gaps",
            "Among 86 clean-eligible units",
            "observed ASR of 45.35\\%",
            "A separate paired four-arm study provides no evidence of a broad risk reduction",
            "none of its 237 valid attacked \\ltwoenabled traces contains a joint-limit step",
            "The claims remain checker-relative",
            "registered joint boundary, frozen attack family, checkpoint, and simulator",
        ),
    )
    require_tokens(
        "introduction contribution summary",
        introduction,
        (
            "In the motivating SABER case",
            "This missing composition exposes two alignment gaps",
            "\\lone aligns trusted task intent with the exact source \\actionblock",
            "\\ltwo aligns the admitted source block with execution",
            "The attack reproduction yields an observed ASR of 45.35\\%",
            "common 75-unit cohort has broad risk-transition rates",
            "Under attack, \\dual task success is 53.33\\%, compared with 60.83\\% for \\vlaonly",
            "237 valid attacked \\ltwoenabled traces",
            "A two-stage cross-layer reference monitor",
            "An attack reproduction and paired system characterization",
        ),
    )
    require_tokens(
        "evaluation primary results",
        evaluation,
        (
            "The complete population contains 60 task/initialization base pairs",
            "Two independently seeded executions of every pair yield 120 seed-specific evaluation units",
            "$120\\times2\\times4=960$ attempts",
            "\\vlaonly is the unchanged runtime baseline",
            "\\loneonly and \\ltwoonly are stage ablations",
            "\\dual is the final composed \\system prototype",
            "Each condition contains 98.96\\% valid traces (475/480)",
            "The four-arm results are therefore nonconfirmatory",
            "A clean trace is eligible if it is valid, achieves strict task success",
            "Clean contact, joint-limit, and force counts need not be zero",
            "Task failure alone is excluded",
            "\\label{tab:task-success}",
            "\\label{tab:risk-transition}",
            "70.83\\% (85/120) & 60.83\\% (73/120)",
            "65.00\\% (78/120) & 53.33\\% (64/120)",
            "52.94\\% (45/85) & 50.67\\% (38/75)",
            "53.85\\% (42/78) & 56.00\\% (42/75)",
            "50.00\\% (43/86) & 48.00\\% (36/75)",
            "55.13\\% (43/78) & 57.33\\% (43/75)",
            "10.92\\% of clean traces (13/119)",
            "14.29\\% of attacked traces (17/119)",
            "4.76\\% (5/105)",
            "form 237 \\ltwoenabled traces",
            "trace-level incidence of 0.00\\% (0/237)",
            "record 4,960 and 2,452 joint-limit steps",
            "All 69 focused transaction and runner cases reach their expected state (100\\%)",
            "performs 78,434 screens",
            "0.41\\% of screens exceed 100\\,ms (323/78,434)",
            "maximum is 458.99\\,ms",
            "maximum-at-most-200\\,ms criterion therefore fails",
            "229.5709",
            "$2.41\\times10^{-5}$\\,rad",
            "force proxy differs from the predispatch shadow-force candidate gate",
            "1.05\\% of valid \\ltwoenabled episodes (5/474)",
            "0.0034\\% of performed screens (5/146,397)",
        ),
    )
    require(
        evaluation.count("\\begin{table}[t]") == 2,
        "evaluation must retain exactly two core result tables",
    )
    require_tokens(
        "conclusion claim summary",
        conclusion,
        (
            "cross-layer reference monitor for two alignment stages",
            "45.35\\% attack-induced risk-transition rate among 86 clean-eligible units (39/86)",
            "120-unit four-arm study",
            "960 episode attempts",
            "98.96\\% valid traces in each condition (475/480)",
            "system comparisons remain nonconfirmatory",
            "common 75-unit cohort",
            "Under attack, task success is 60.83\\% for \\vlaonly and 53.33\\% for \\dual",
            "237 valid attacked \\ltwoenabled traces",
            "record 4,960 and 2,452 such steps",
            "does not establish a broad robot-safety improvement",
        ),
    )

    forbidden_active_tokens = (
        "13/18",
        "0/18",
        "cluster-bootstrap CI",
        "95\\% CI",
        "tab:main-results",
        "<<<<<<<",
        ">>>>>>>",
    )
    forbidden_hits = [token for token in forbidden_active_tokens if token in joined]
    require(
        not forbidden_hits,
        f"active paper source contains forbidden legacy tokens: {forbidden_hits}",
    )

    require(SUBMISSION_METADATA.is_file(), "HotCRP copy/paste metadata sheet is missing")
    metadata = SUBMISSION_METADATA.read_text(encoding="utf-8")
    normalized_metadata = re.sub(r"\s+", " ", metadata)
    require(
        "opens on 15 August 2026" in normalized_metadata
        and "https://ndss27-fall.hotcrp.com/" in normalized_metadata,
        "HotCRP metadata must retain the official Fall opening date and site",
    )
    metadata_tokens = (
        "ProofAlign: Cross-Layer Runtime Integrity for Embodied",
        "intent–action authorization gap",
        "action–execution realization gap",
        "Among 86 clean-eligible units",
        "observed ASR is 45.35%",
        "960 episode attempts",
        "98.96% valid traces (475/480)",
        "comparisons remain nonconfirmatory",
        "50.67%, 56.00%, 48.00%, and 57.33%",
        "Dual task success is 53.33%, compared with 60.83% for VLA-only",
        "237 valid attacked L2-enabled traces",
        "0.00% contain a joint-limit step",
        "LaTeX/TikZ diagrams",
    )
    missing_metadata = [
        token for token in metadata_tokens if token not in normalized_metadata
    ]
    require(
        not missing_metadata,
        f"HotCRP metadata sheet drifted or is incomplete: {missing_metadata}",
    )
    if "GPT-5 family" in disclosure or "GPT-5 model family" in disclosure:
        pending.append("confirm the exact Codex/model label shown at submission time")
    return pending


def validate_pdf() -> None:
    require(PDF.is_file(), f"compiled PDF missing: {PDF}")
    info = run_checked("PDF metadata readable", ["pdfinfo", str(PDF)], cwd=PAPER_ROOT)
    require(
        re.search(r"^Pages:\s+15$", info, re.M) is not None,
        "PDF must remain 15 total pages with technical content ending on page 13",
    )
    require(
        re.search(r"^Page size:\s+612 x 792 pts \(letter\)$", info, re.M) is not None,
        "PDF is not US Letter",
    )
    for field in ("Author", "Title", "Subject", "Keywords"):
        match = re.search(rf"^{field}:\s*(.*)$", info, re.M)
        require(match is None or not match.group(1).strip(), f"PDF metadata leaks {field}")

    technical_tail = run_checked(
        "PDF pages 12--13 text readable",
        [find_poppler_tool("pdftotext"), "-f", "12", "-l", "13", str(PDF), "-"],
        cwd=PAPER_ROOT,
    )
    excluded_pages = run_checked(
        "PDF excluded pages 14--15 text readable",
        [find_poppler_tool("pdftotext"), "-f", "14", "-l", "15", str(PDF), "-"],
        cwd=PAPER_ROOT,
    )
    require("CONCLUSION" in technical_tail.upper(), "Conclusion must begin by page 13")
    require(
        all(
            token in technical_tail.upper()
            for token in ("GENERATIVE-AI DISCLOSURE", "ETHICS CONSIDERATIONS", "REFERENCES")
        ),
        "pages 12--13 must contain the conclusion followed by disclosure, ethics, and references",
    )
    forbidden_excluded_pages = (
        "IX. CONCLUSION",
        "VII. SECURITY ANALYSIS AND DISCUSSION",
        "VIII. RELATED WORK",
        "VI. EVALUATION",
    )
    require(
        not any(
            token in excluded_pages.upper()
            for token in forbidden_excluded_pages
        ),
        "pages 14--15 must contain only references",
    )

    require(LOG.is_file(), f"LaTeX log missing: {LOG}")
    log = LOG.read_text(encoding="utf-8", errors="replace")
    forbidden = (
        "Overfull \\hbox",
        "Overfull \\vbox",
        "Undefined control sequence",
        "There were undefined references",
        "Citation `",
        "LaTeX Error",
        "Emergency stop",
        "Fatal error",
    )
    hits = [token for token in forbidden if token in log]
    require(not hits, f"LaTeX log contains forbidden diagnostics: {hits}")

    fonts = run_checked(
        "PDF font table readable", [find_pdffonts(), str(PDF)], cwd=PAPER_ROOT
    )
    font_rows = [
        line.split()
        for line in fonts.splitlines()[2:]
        if line.strip() and not set(line.strip()) <= {"-"}
    ]
    require(font_rows, "PDF font table is empty")
    require(
        all(len(row) >= 6 and row[-5:-3] == ["yes", "yes"] for row in font_rows),
        "every PDF font must be embedded and subset",
    )
    require(
        "TeXGyreTermes" in fonts and "NewTX" in fonts,
        "PDF must retain Times-compatible text and NewTX math fonts",
    )
    print(
        "PASS  PDF is 15 total pages on US Letter; technical content ends on page 13, "
        "pages 14--15 contain only references, "
        "and metadata, fonts, and log pass"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--final",
        action="store_true",
        help="fail on submission-time placeholders that are warnings during drafting",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="validate the existing PDF instead of invoking Tectonic",
    )
    args = parser.parse_args()

    try:
        run_checked(
            "LaTeX source tree and resolved citations",
            ["ruby", "scripts/check_source.rb"],
            cwd=PAPER_ROOT,
        )
        run_checked(
            "frozen claim/evidence and Lean-name audit",
            [sys.executable, "scripts/audit_ndss2027_paper_claims.py"],
            cwd=ROOT,
        )
        tests = run_checked(
            "focused L2a/runner negative-integrity tests",
            ["uv", "run", "pytest", "-q", *NEGATIVE_TESTS],
            cwd=ROOT,
        )
        require("69 passed" in tests, "focused test count drifted from 69")
        run_checked("Lean transaction model", ["lake", "build"], cwd=ROOT / "lean")
        if not args.skip_build:
            run_checked(
                "Tectonic manuscript build",
                [
                    "tectonic",
                    "-X",
                    "compile",
                    "paper_ndss.tex",
                    "--outdir",
                    "build",
                    "--keep-intermediates",
                    "--keep-logs",
                ],
                cwd=PAPER_ROOT,
            )
        pending = validate_source_structure()
        print("PASS  anonymous source structure and section order")
        validate_pdf()
        if pending:
            for item in pending:
                print(f"PENDING  {item}")
            require(not args.final, "submission-time placeholders remain")
    except AssertionError as error:
        print(f"FAIL  {error}", file=sys.stderr)
        return 1

    print("NDSS 2027 manuscript preflight: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
