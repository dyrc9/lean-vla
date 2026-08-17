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


def find_pdffonts() -> str:
    executable = shutil.which("pdffonts")
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
            "native/poppler/poppler/bin/pdffonts",
            "native/poppler/bin/pdffonts",
        ):
            candidate = dependency_root / relative
            if candidate.is_file():
                return str(candidate)
    raise AssertionError("PDF font audit: required executable not found: pdffonts")


def validate_source_structure() -> list[str]:
    main = MAIN.read_text(encoding="utf-8")
    require("\\author{}" in main, "anonymous submission must keep \\author{}")
    require("\\pagestyle{plain}" in main, "submission must retain page numbers")
    ordered = (
        "\\input{sections/conclusion}",
        "\\input{sections/ai_disclosure}",
        "\\input{sections/ethics}",
        "\\bibliographystyle{IEEEtran}",
        "\\appendix",
    )
    positions = [main.find(token) for token in ordered]
    require(all(position >= 0 for position in positions), "required paper sections missing")
    require(positions == sorted(positions), "conclusion/disclosure/ethics/references/appendix order drifted")

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
        "reviewed the generated text and diagrams" in disclosure,
        "Generative-AI disclosure must retain author-review responsibility",
    )
    require(
        "all manuscript sections" in disclosure and "Figs.~1--3" in disclosure,
        "Generative-AI disclosure must identify the generated prose/figure scope",
    )
    design = re.sub(r"\s+", " ", DESIGN.read_text(encoding="utf-8"))
    implementation = re.sub(
        r"\s+", " ", IMPLEMENTATION.read_text(encoding="utf-8")
    )
    require(
        "first compiles $C_t$" in design
        and "triggered L2b screen qualifies" in design
        and design.index("first compiles $C_t$")
        < design.index("triggered L2b screen qualifies")
        < design.index("The dispatch boundary verifies"),
        "design must preserve contract -> optional screen -> authorization order",
    )
    runtime_order = (
        "policy output",
        "assessment",
        "contract construction",
        "optional guard screening",
        "authorization",
        "dispatch",
        "receipts",
        "effects",
    )
    runtime_clause = implementation[
        implementation.index("a runtime wrapper orders") :
    ]
    runtime_positions = [runtime_clause.index(token) for token in runtime_order]
    require(
        runtime_positions == sorted(runtime_positions),
        "implementation module order drifted from the integrated transaction",
    )
    require(
        "complete mediation is conditional on the TCB" in implementation
        and "uninstrumented actuator path" in implementation,
        "reference-monitor prose must retain the deployment bypass boundary",
    )
    require(
        "fresh nonce" not in design
        and "fresh one-use authorization bound to the episode nonce" in design,
        "design must distinguish the episode nonce from each fresh authorization",
    )
    ethics = re.sub(r"\s+", " ", ETHICS.read_text(encoding="utf-8"))
    require(
        "no human subjects, personal data, or undisclosed real-system vulnerability"
        in ethics,
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
            "39 of 86",
            "45.35\\%",
            "[32.93\\%, 57.78\\%]",
            "11/18 tasks",
            "13/18",
            "4/18, 1/18, 0/18, and 0/18",
            "39.79\\,ms",
            "18.30\\,ms p95",
            "no 100\\,ms miss",
            "frozen attack family and simulator setting",
        ),
    )
    require_tokens(
        "introduction contribution summary",
        introduction,
        (
            "paired 144-episode study",
            "L1-only records 13/18 task success under both clean and attacked inputs",
            "L2-on arms record zero observed joint-limit crossings",
            "Dual combines these sample outcomes",
            "does not recover a model's latent intent",
            "establish real-robot safety",
        ),
    )
    require_tokens(
        "evaluation primary results",
        evaluation,
        (
            "39/86=45.35\\%",
            "4/18 (22.22\\%)",
            "1/18 (5.56\\%)",
            "6438.1998<10000",
            "39.79\\,ms",
            "18.30\\,ms",
            "100\\,ms miss rate is zero",
            "preregistered Bonferroni correction",
            "permits at most a 20-percentage-point task-success loss",
            "not a deployment-derived utility threshold",
            "MuJoCo generalized-constraint-force value",
            "not a calibrated end-effector force",
            "checks execution/restore consistency",
            "not prediction under dynamics mismatch",
            "VLA-only is the unchanged runtime baseline",
            "not a claim of outperforming every VLA safety system",
            "authorization--receipt--effect transaction",
        ),
    )
    require_tokens(
        "conclusion claim summary",
        conclusion,
        (
            "39/86 (45.35\\%)",
            "successfully reproduces SABER",
            "13/18 attacked task success",
            "0/18 observed joint-limit violation episodes",
            "frozen simulator setting",
            "hard-real-time analysis",
        ),
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
        "ProofAlign: Trusted-Task Monitoring and Cross-Layer Execution Integrity",
        "39 of 86",
        "45.35%",
        "[32.93%, 57.78%]",
        "18 held-out pairs",
        "144-episode",
        "11/18",
        "13/18",
        "4/18, 1/18, 0/18, and 0/18",
        "39.79 ms",
        "18.30 ms p95",
        "100 ms miss",
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
        re.search(r"^Pages:\s+13$", info, re.M) is not None,
        "PDF must remain 13 total pages",
    )
    require(
        re.search(r"^Page size:\s+612 x 792 pts \(letter\)$", info, re.M) is not None,
        "PDF is not US Letter",
    )
    for field in ("Author", "Title", "Subject", "Keywords"):
        match = re.search(rf"^{field}:\s*(.*)$", info, re.M)
        require(match is None or not match.group(1).strip(), f"PDF metadata leaks {field}")

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
        "PASS  PDF is 13 total pages on US Letter with anonymous metadata, embedded/subset "
        "fonts, and a clean log"
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
            "LaTeX source tree and 38 citations",
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
