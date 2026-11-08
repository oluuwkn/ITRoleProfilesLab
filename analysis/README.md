# Reproducible analysis of IT role technology rankings

This package contains executed analyses, aggregate tables, and the manuscript builder.
It does not contain respondent microdata, the original repository, or an independent
occupational validation set.

## Inputs

- User-supplied `survey_results_public.csv`, 49,191 rows and 172 columns.
- CSV SHA-256: `2d1f65308877282edfb4470520eabbc08cb499118432a3dcec6a66c086aa2baa`.
- The uploaded GitHub ZIP has archive comment commit
  `4c1a665929179b0dd0ddc7bb06e95e2b5e85b1af`.
- Its saved comparison file is
  `data/processed/skill_weights_by_role_final_v2.csv`.
- The source algorithm is `data/scripts/01_build_skill_weights.py`;
  the four manual additions are in `02_append_ml_skills.py`.

The archive comment is an identifier recorded from the uploaded ZIP, not a claim
that a remote commit or its signatures were independently verified.

## Run

Use Python with NumPy, pandas, and SciPy. Exact executed versions are in
`results/audit.json`.

```bash
python run_analysis.py \
  --csv /path/to/survey_results_public.csv \
  --saved /path/to/skill_weights_by_role_final_v2.csv \
  --out results --bootstrap 1000 --seed 2026
```

The script reads its inputs without modifying them. Allow several minutes.
The manuscript builder additionally requires python-docx:

```bash
python build_manuscript.py
```

It loads `results` beside the builder and writes `article_revised.docx` in
the parent directory. `run.log` records the completed execution. Public
archival publication has not been performed.

## Design

- Seven roles selected by exact DevType value; equality with original substring
  selection is checked on the supplied file.
- Four question categories; category and technology name jointly identify an item.
  Binary selections per respondent; missing answers excluded per question.
- Main frequency p = selectors / valid question respondents.
  Alternative f = mentions / all selections in the question.
- For each convention, ratios use its own corresponding background denominator.
- Five methods: frequency, ratio, frequency * ln(1+ratio),
  frequency * sqrt(ratio), frequency * ratio.
- Threshold grid 0.01, 0.025, 0.04, 0.05, 0.10. The primary p threshold is 0.04.
- Both inclusive and role-excluded backgrounds, and full versus common-answer cohorts.
- Resampling: 1,000 bootstrap samples with replacement, stratified by every
  observed DevType including missing, fixing stratum sizes, seed 2026.
  Role frequencies and the inclusive full background are recomputed jointly.
  Bootstrap is run at the primary threshold, not at every grid threshold.
- Stability compares the original and resampled rankings using common-set
  Spearman/Kendall, selected-set Jaccard, top-5/top-10 Jaccard, and a finite-depth
  prefix agreement diagnostic. Top-k includes all ties at the cutoff.
- Paired differences compare correlations of Slog with frequency and ratio on
  both the fixed original set and each resampled selected set. Quantiles are
  percentile intervals conditional on the observed stratum sizes; no family-wise
  multiplicity correction or random technology resampling is used.

## Prefix diagnostic

`prefix_b_10` is the normalized weighted observed component of RBO-b, not the
extrapolated infinite RBO. Let t and b be a technology's first and last rank
in its tie block. At depth d, its contribution is clipped (d-t+1)/(b-t+1).
Missing technologies contribute zero. Agreement is the cosine of the two
contribution vectors (Corsi and Urbano, 2024, equations 8 and 11).

We average agreement at d=1..D with weights (1-rho)*rho**(d-1), normalized by
their sum; D=min(10, list lengths), rho=0.9. `prefix_depth` records D. Scores
from different D do not refer to the same depth horizon. Design comparisons
also export persistence 0.8 and 0.95. This explicit finite-depth choice avoids
assuming unobserved continuations of lists of different lengths.

## Outputs

| File | Content |
| --- | --- |
| audit.json | Fingerprint, sample checks, versions, and legacy reproduction |
| respondents.csv | Role totals, per-question answering counts, complete cases |
| legacy_reproduced.csv | Recomputed original survey pairs, full scores and exported rounded columns |
| technology_counts.csv | All technology counts and both denominators by role, category and cohort |
| scores_full_precision.csv | Five unrounded scores for all denominator/background/cohort designs |
| method_correlations.csv | Every method pair, role, category/pooled scope, threshold and design |
| top5.csv | Tie-expanded top-5 records at threshold 0.04 for all designs and methods |
| threshold_sensitivity.csv | Set/order/top-k comparison with threshold 0.04, full cohort and inclusive background |
| design_effects.csv | Denominator, background and common-answer comparisons, with persistence sensitivity |
| variance_decomposition.csv | Both variance terms, twice covariance, shares, and identity residual |
| bootstrap_metrics.csv.gz | Per-replicate selection and ranking stability |
| bootstrap_paired_correlations.csv.gz | Per-replicate correlations and paired differences |
| bootstrap_stability_summary.csv | Medians and 2.5/97.5 percentiles by method, role, and scope |
| bootstrap_correlation_summary.csv | Individual correlation and paired-difference percentile intervals |
| bootstrap_inclusion_probabilities.csv | Selection and pooled top-10 inclusion probabilities |

`all_categories` denotes a pooled diagnostic. It is not an occupational ranking
that assigns comparable professional importance across questionnaire categories.
The other scopes are the four questionnaire categories.

`denominator_fixed_p_set` keeps p>=0.04 for both scores; `denominator_own_sets`
allows p>=0.04 and f>=0.04 to select different sets. `background_excluded`
keeps the same selected set. `complete_cases_own_sets` recalculates frequencies,
background and selection within respondents answering all four questions.

Undefined correlations remain missing. Counts of valid bootstrap replicates are
reported per summary metric. An empty union has undefined Jaccard, not perfect
agreement. Items with zero background counts have undefined ratios, not a
silently inserted smoothing constant.

## Validation and limitations

The run asserts exact matching of all 228 legacy keys, agreement of rounded
frequency and ratio columns, normalized-weight error below 1e-12, and the
variance-decomposition identity. Boundary checks cover identical tied lists
and disjoint lists for the finite prefix diagnostic.

The official website reports 49,009 responses in its published analysis. This
file has 49,191 unique IDs, no complete-row duplicates, and no consent field.
The exact website inclusion set and explanation for the 182-row discrepancy
have not been established; no rows are removed merely to match the total.

Bootstrap stability is not occupational validity. The package contains no
expert judgments, independent vacancies, proficiency measurements, candidate
matching experiment, or explanation-usability experiment. Manual project
requirements are not independent validation of weights used to create them.

For a future expert design, the p>=0.01 lists contain 132 Backend and 113
Frontend technologies; those are measured list sizes, not an assumption about
an acceptable expert workload.

## Sources

- Stack Overflow methodology: https://survey.stackoverflow.co/2025/methodology
- Technology questions: https://survey.stackoverflow.co/2025/technology
- Corsi and Urbano: https://arxiv.org/abs/2406.07121
- Webber, Moffat, Zobel: https://doi.org/10.1145/1852102.1852106
