# Reproducible analysis: technology profiles of IT roles (Stack Overflow Developer Survey 2025)

One script, `run_analysis.py`, produces every number reported in the manuscript. Respondent microdata are not redistributed.

## Inputs
- `survey_results_public.csv` — Stack Overflow Developer Survey 2025, 49,191 rows, 172 columns. SHA-256: `2d1f65308877282edfb4470520eabbc08cb499118432a3dcec6a66c086aa2baa`
- Optional: `skill_weights_by_role_final_v2.csv` from the project repository (`data/processed/`), produced by `data/scripts/01_build_skill_weights.py`. Used only to verify that the legacy 228-pair table is reproduced exactly.

## Run
```bash
pip install -r requirements.txt
python run_analysis.py --csv survey_results_public.csv \
    --saved skill_weights_by_role_final_v2.csv --out results \
    --bootstrap 1000 --seed 2026 --controls 1000 --control-seed 2027
python make_manifest.py
```
Seeds and replicate counts were fixed before inspecting new estimates. Expect several minutes.

## Where each manuscript element comes from
| Manuscript element | Output file |
|---|---|
| Data audit, 49,191 rows, 182-row difference, complete cases | `results/audit.json` |
| Table I, Table II (answering counts, complete answers) | `results/respondents.csv` |
| Counts c, N, M per role, category, technology | `results/technology_counts.csv` |
| Eq. (1)–(3): p, f, L, Slog, Sroot, Slin, both backgrounds | `results/scores_full_precision.csv` |
| Reproduction of 228 legacy pairs | `results/legacy_reproduced.csv`, `audit.json` → `legacy` |
| Table II a: m = M/N and equivalent p thresholds, eq. (1a) | `results/equivalent_thresholds.csv` |
| Within-category invariance; min Spearman of Slog (p vs f) | `results/denominator_within_category.csv`, `audit.json` → `revision` |
| Correlations among the five rules (pooled and per category) | `results/method_correlations.csv` |
| Eq. (4)–(5): variance decomposition | `results/variance_decomposition.csv` |
| Threshold grid, Jaccard, RBO-b prefix | `results/threshold_sensitivity.csv` |
| Minimum p within top-10 (margin to threshold) | `results/top10_threshold_margin.csv` |
| Bootstrap: raw replicates and percentile summaries | `results/bootstrap_metrics.csv.gz`, `results/bootstrap_stability_summary.csv` |
| Exact top-10 retention with Monte Carlo SE (e.g. Backend 53.6% / 97.3% / 99.0%) | `results/bootstrap_top10_retention.csv` |
| Paired correlation differences | `results/bootstrap_correlation_summary.csv` |
| Inclusion probabilities | `results/bootstrap_inclusion_probabilities.csv` |
| Eq. (6): role-excluded background; complete-answer cohort | `results/design_effects.csv` |
| Section II F: controls A (records) and B (answerers) | `results/control_replicates.csv.gz`, `results/control_comparison.csv` |
| Top-5 lists | `results/top5.csv` |

## Definitions used in the code
- p = c/N (share of respondents answering the question), f = c/M (share of selections).
- L = role frequency / background frequency, same denominator convention on both sides.
- Slog = p·ln(1+L), Sroot = p·√L, Slin = p·L.
- Background `inclusive`: all respondents of the file answering the question; `excluded`: the same without the current role.
- Control A: from the full file, the same number of records per DevType stratum as in the complete-answer cohort. Control B: per question, among valid answerers, the exact complete-cohort count per DevType stratum; questions sampled independently, only within-category comparisons are interpreted.
- `share_le_observed` in `control_comparison.csv`: proportion of control replicates whose agreement with the full-file ranking is at or below the observed complete-cohort agreement.

## Software
Executed versions are recorded in `results/audit.json`; `requirements.txt` pins the versions used for the reported results.
