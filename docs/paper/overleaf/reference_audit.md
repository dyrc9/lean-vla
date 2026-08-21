# Reference metadata provenance audit

Audit date: 2026-08-20

## Source policy

1. Use a venue or publisher's downloadable BibTeX/Citation record as the source of record.
2. If no exporter exists, use the official paper page and the final paper PDF.
3. For preprints, use the arXiv API and the canonical arXiv URL.
4. Use DOI registration metadata and DBLP only as cross-checks, not as silent overrides of venue metadata.
5. Normalize only local citation keys, capitalization braces, names with obvious case/spacing errors, and LaTeX escaping required by IEEEtran.

## Coverage

| Source of record | Citation keys | Count |
|---|---|---:|
| arXiv API | `saber2026`, `liberosafety2026`, `safevlabench2026`, `foresightsafety2026`, `vlasafety2026`, `freezevla2025`, `covervla2026`, `robosuite2020` | 8 |
| PMLR official BibTeX | `pi05`, `safetychance2024`, `measurementrobustcbf2021`, `realizableshields2025` | 4 |
| RSS official BibTeX | `rth2024`, `vlmpc2024` | 2 |
| ICLR/NeurIPS official BibTeX | `badrobot2025`, `safevla2025`, `safe2025` | 3 |
| IEEE publication/DOI records | `robopair2025`, `agentpermissions2026`, `webplugins2026`, `scaphy2023`, `saltzer1975`, `mujoco2012` | 6 |
| USENIX official paper pages/BibTeX | `struq2025`, `agenticsok2026`, `attriguard2026`, `mate2026`, `adaptivesecond2026`, `cfaplus2024`, `arto2026`, `tat2026` | 8 |
| NDSS official paper pages and final-PDF DOI | `isolategpt2025`, `ace2026`, `saga2026`, `lesdissonances2026`, `toolhijacker2026`, `obliinjection2026`, `diat2019` | 7 |
| ACM publication/DOI records | `secalign2025`, `schneider2000` | 2 |
| Springer official `.BIB` download | `lean4` | 1 |
| Official conference program/author project page plus arXiv | `sealvla2026`, `camel2026` | 2 |
| **Total** |  | **43** |

Every entry in `paper.bib` contains a canonical official paper, publisher, DOI, or arXiv URL.
An automated link check returned a 2xx response for 41/43 targets.  The two ACM DOI targets resolve to the correct ACM Digital Library records but reject automated HEAD requests with Cloudflare HTTP 403; their DOI registration metadata was independently verified.

## Resolved conflicts and exceptions

- `saber2026`: the arXiv API contains no IROS proceedings metadata. The BibTeX entry therefore cites only arXiv. The authors' homepage reports IROS 2026 acceptance, but this is kept in prose as an author-reported status rather than encoded as a published proceedings entry.
- `safevla2025` and `safe2025`: NeurIPS's official **Bibtex** downloads and the DOI deposits currently disagree on page ranges. Per the requested precedence rule, `paper.bib` uses the NeurIPS-exported ranges (`153335--153373` and `40041--40076`) and records the conflict in comments.
- `covervla2026`: the reference is kept as arXiv. The official ScaleBot OpenReview record supports the workshop version; an ECCV proceedings claim is not encoded in the BibTeX entry.
- `sealvla2026`: the ICRA program and author project page confirm the venue, but no stable IEEE proceedings DOI/page range was found. The entry therefore retains the official arXiv link and omits invented DOI/pages.
- Some official exports contain obvious mechanical defects (for example, an unescaped `&` or a missing space in an author name). These are corrected only for valid LaTeX and author-name rendering; bibliographic facts are not changed.

## Build validation

The bibliography was rebuilt with the NDSS-provided `IEEEtran.cls`, stock
`IEEEtran` bibliography style, and the standard `url` package with its
`hyphens` line-breaking option after the audit. The generated `.bbl` contains
all 43 cited entries with no BibTeX warning, undefined citation, duplicate key,
or overfull box. The NDSS-required IEEEtran 1.8b class and margins are retained;
the source explicitly loads Times-compatible TeX Gyre Termes text and NewTX
mathematics fonts so Tectonic and Overleaf do not silently diverge.
