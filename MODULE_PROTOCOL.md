# Module Protocol

How to create and document numbered science modules in this project.

---

## Folder Naming

Each module gets a zero-padded three-digit prefix and a short snake_case descriptor:

```
NNN_descriptor/
```

Examples from this project:

| Folder | What it covers |
|--------|---------------|
| `001_validation` | DES-SEIR convergence validation |
| `002_agent_based_des` | Agent-based DES with intelligent actors |
| `003_absdes_providers` | Healthcare provider impact on DES |
| `004_multicity` | Multi-city ODE metapopulation |
| `005_multicity_des` | Multi-city DES metapopulation |

**Rules:**

- Number sequentially from the last existing module (`ls -d [0-9]*/` to check).
- The descriptor should be 1-3 words, enough to distinguish purpose at a glance.
- Never reuse a number, even if a module is abandoned. Gaps are fine.

---

## Folder Contents

Every module folder contains at minimum:

```
NNN_descriptor/
├── REPORT_descriptor.md   # The scientific report (required)
├── results/               # Generated figures and data (required)
│   ├── 01_figure_name.png
│   └── ...
├── main_script.py         # Primary validation / figure-generation script
└── supporting_modules.py  # Any library code the script imports
```

Optional:

```
├── data/                  # Input data files (GeoJSON, CSV, etc.)
├── plan.md                # Design plan (if the module was planned before coding)
└── __pycache__/           # Ignored by git
```

---

## Report File

### Naming

```
REPORT_descriptor.md
```

The descriptor matches the folder's descriptor. Examples:

| Folder | Report file |
|--------|-------------|
| `001_validation` | `REPORT_validation.md` |
| `002_agent_based_des` | `REPORT_agent_based_des.md` |
| `005_multicity_des` | `REPORT_multicity_des.md` |

This makes reports uniquely identifiable when opened outside the folder context
(e.g. in a flat search, an editor tab bar, or a combined PDF).

### Structure

Every report follows this skeleton. Sections can be omitted if truly not
applicable, but the ordering is fixed.

```markdown
# Title — one line describing the scientific finding

## Overview

2-4 paragraphs: what this module does, why it exists, and the core findings
as numbered bullet points. A reader who stops here should understand the
headline result.

---

## Motivation / Why This Approach

Why this module exists relative to what came before. What problem the
predecessor left unsolved.

## Method

### Model description

The scientific method, written for a literate reader who hasn't seen the code.
Include equations, parameter tables, and architecture diagrams (as ASCII or
embedded images) as needed.

### Implementation notes

Brief code-level notes: key files, entry points, run instructions.
Reference specific files and line numbers where helpful:
`city_des.py:118-147`.

## Results

### Figure N: Short title

For each figure:
1. What the figure shows (one sentence).
2. The figure itself (embedded image from `results/`).
3. A results table if quantitative.
4. Interpretation (2-3 sentences).

Number figures sequentially within the module: Figure 1, Figure 2, etc.

### Summary of findings

A concise numbered list of the key scientific takeaways.

---

## Validation

How the results were checked. What convergence criteria, baselines, or
sanity checks were applied.

## Limitations and Next Steps

What this module does NOT capture. What the natural follow-on work is.

## Code Reference

| File | Purpose |
|------|---------|
| `main_script.py` | Entry point, produces all figures |
| `supporting_module.py` | Core simulation logic |

## Appendix (optional)

Derivations, extended parameter tables, or supplementary figures.
```

### Writing Guidelines

1. **Self-contained**: The report should be readable without running any code.
   Embed figures as `![caption](results/NN_name.png)`.

2. **Quantitative**: State numbers, not just qualitative impressions.
   "Peak infection reduced from 4.7% to 2.2% (54% reduction)" not
   "providers helped a lot."

3. **Honest about noise**: If results are within stochastic variation, say so.
   Report the number of Monte Carlo runs and note where confidence is low.

4. **Parameters are explicit**: Include a table of every parameter used.
   A reader should be able to reproduce the experiment from the report alone.

5. **Figures are numbered and captioned**: Every figure has a number, a short
   title, and at minimum one sentence of interpretation.

6. **Cross-reference predecessors**: Cite earlier modules by number:
   "Module 003 demonstrated that..." This builds a traceable chain of evidence.

7. **No forward promises**: Describe what WAS done, not what WILL be done
   (except in the Limitations/Next Steps section).

---

## Figure Naming

Figures go in `results/` with a two-digit prefix matching their report order:

```
results/
├── 01_des_vs_ode_comparison.png
├── 02_convergence_by_population.png
├── 03_health_modulated_r0.png
├── 04_provider_density.png
└── 05_spatial_map_deaths.png
```

**Rules:**
- Zero-padded two digits so they sort correctly.
- Snake_case descriptor, brief but distinguishing.
- PNG format for all figures (vector quality from matplotlib's default DPI).

---

## Creating a New Module — Checklist

1. Determine the next number: `ls -d [0-9]*/ | tail -1`
2. Create the folder: `mkdir NNN_descriptor`
3. Create `results/` inside it: `mkdir NNN_descriptor/results`
4. Write code that produces figures into `results/`.
5. Write `REPORT_descriptor.md` following the structure above.
6. Verify: can a reader understand the findings from the report alone,
   without running code?

---

## Renaming Legacy Reports

Existing modules use `REPORT.md` (without descriptor). These can be renamed
to follow the new convention as they are next touched:

```
001_validation/REPORT.md        → REPORT_validation.md
002_agent_based_des/REPORT.md   → REPORT_agent_based_des.md
003_absdes_providers/REPORT.md  → REPORT_absdes_providers.md
004_multicity/REPORT.md         → REPORT_multicity.md
005_multicity_des/REPORT.md     → REPORT_multicity_des.md
```

No rush — do it when the report is next edited.
