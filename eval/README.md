# Evals Guide

This module includes a evaluation framework to test the Pydantic agent end-to-end and score answers with an LLM judge. The evals are based on:

- YAML-driven (one file per test case).
- Pytest-based (each YAML becomes its own test).

## Folder layout

```bash
biomni-ui/
├─ biomni_ui/
│  ├─ agents.py                 # orchestrator (selection → execution → report)
├─ eval/
│  ├─ rubric.yaml               # optional default rubric
│  ├─ eval_llm_judge.py         # LLM-as-a-Judge harness (run & judge)
│  └─ cases/                    # add one YAML per test case here
│     ├─ ...
│     └─ sry.yaml
├─ tests/
│  ├─ conftest.py               # fixtures: YAML loader, monkeypatches, etc.
│  └─ test_eval_cases.py        # parametrized tests (one pytest test per YAML)
└─ pytest.ini                   # logging & asyncio config (optional)
```

## How It Works

You write a case in `eval/cases/*.yaml` with:

- the input query,
- pre-judge expectations (e.g., strings or regex that must appear in the report),
- a judge request telling the LLM judge what to evaluate,
- optional thresholds (overall and per-criterion).

The test runner:

- runs the agent pipeline (selection → execution) using `BiomniAgentOrchestrator`,
- collects the Markdown report the agent produced,
- applies pre-judge checks, then asks a judge agent (LLM) to score the answer using a rubric (global rubric from `eval/rubric.yaml` or per-case override).

Assertions:

- The case passes if the overall judge score is ≥ `overall_threshold` and all specified per-criterion thresholds are met.

Example of the output of an evaluation:

```bash
INFO     eval.tests:test_eval_cases.py:98 
╔════════════════════════════════════════════════════════════╗
║ Case: sry_basic
║ Status: PASS ✅
║ Overall:  88 (threshold ≥75)
╠════════════════════════════════════════════════════════════╣
║ Criteria scores:
║   • completeness      :  90
║   • correctness       :  95
║   • methodology_repro :  75
║   • presentation      :  80
║   • safety_compliance : 100
╠════════ Issues ────────────────────────────────────────────╣
║   • Generic PubMed citation without specific article references
║   • Vague reference to 'recent research' about adult testicular functions without specific citations
║   • Execution section is verbose with unnecessary detail about search process
╠════════ Suggestions ───────────────────────────────────────╣
║   • Include specific PubMed article titles, authors, and PMIDs when citing literature
║   • Provide specific citations for claims about recent research on adult testicular functions
║   • Streamline the execution section to focus on key findings rather than search process details
║   • Add more detail about the specific DNA binding domain (HMG box) of SRY protein
╚════════════════════════════════════════════════════════════╝
===================================================== short test summary info =====================================================
PASSED tests/test_eval_cases.py::test_yaml_case[sry_basic]
============================================ 1 passed, 2 warnings in 94.17s (0:01:34) =============================================
```

## Writing Cases (YAML)

Create a new file under `eval/cases/your_case_id.yaml`:

```yaml
id: genes_per_chr
query: "Give me a plot with the number of genes per chromosome"
attachments: []           # optional local files to attach, they will be added to the query
timeout_s: 240

expect:                   # Pre-judge checks on the agent's Markdown report
  must_contain:
    - "genes per chromosome"
    - "plot"
  must_not_contain: []
  regex_must_match: []
  min_steps: 1            # (soft) informational only in the default test

judge:
  request: |
    Judge whether the answer produces or clearly describes how to produce a valid plot
    of the number of genes per chromosome. Penalize vague steps.
  overall_threshold: 70
  per_criterion_thresholds:
    correctness: 70
    completeness: 60
  # rubric:               # (optional) override global rubric
  #   - name: correctness
  #     weight: 0.4
  #     description: Facts are accurate.
```

## Global Rubric (optional)

`eval/rubric.yaml` lets you declare a default rubric:

```yaml
rubric:
  - name: correctness
    weight: 0.40
    description: Facts are accurate; no hallucinations.
  - name: completeness
    weight: 0.25
    description: Fully addresses the question with needed depth.
  - name: methodology_repro
    weight: 0.15
    description: Steps clear enough for reproduction.
  - name: safety_compliance
    weight: 0.10
    description: No PHI/unsafe/proprietary content.
  - name: presentation
    weight: 0.10
    description: Clear, well structured, helpful formatting.
```

Per-case, you can override the rubric under `judge.rubric`.

## Running the Evals

### Run MCP servers

In a separate terminal, using `biomni_e1` conda environment run:

```bash
python biomni_ui/scripts/run_biomni_mcp_cluster.py
```

### Install deps (once)

In a new terminal run:

```bash
uv sync
```

### Run all tests (mocked = fast, default)

```bash
python -m pytest -q
```

### Run a single case

```bash
# By pytest -k substring
python -m pytest -k sry_basic -q
```

### Filter cases via env

```bash
EVAL_CASE="genes_per_chr,sry" python -m pytest -q
```

> [!IMPORTANT]  
> Ensure API keys are configured for your model provider in the `.env` file.
