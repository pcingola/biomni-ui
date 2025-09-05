import os
import re
import asyncio
from pathlib import Path

import pytest
import yaml
import logging

from eval.eval_llm_judge import (
    run_question_with_orchestrator,
    judge_answer,
    RubricCriterion,
)

# Basic logging (respects pytest’s --log-cli-level too)
logging.basicConfig(
    level=os.getenv("EVAL_LOG_LEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("eval.tests")

REPO_ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = REPO_ROOT / "eval" / "cases"
RUBRIC_FILE = REPO_ROOT / "eval" / "rubric.yaml"

def _load_rubric():
    if RUBRIC_FILE.exists():
        data = yaml.safe_load(RUBRIC_FILE.read_text())
        return data.get("rubric")
    return None

def _load_cases():
    cases = []
    for yf in sorted(CASES_DIR.glob("*.yaml")):
        case = yaml.safe_load(yf.read_text())
        if "id" not in case:
            case["id"] = yf.stem
        cases.append(case)

    # Optional filter: EVAL_CASE="id1,id2" or any substring match
    flt = os.getenv("EVAL_CASE")
    if flt:
        needles = [s.strip() for s in flt.split(",") if s.strip()]
        cases = [c for c in cases if any(n in c["id"] for n in needles)]
    return cases

RUBRIC_YAML = _load_rubric()
CASES = _load_cases()
if not CASES:
    raise RuntimeError(f"No YAML cases found in {CASES_DIR}")

def _assert_text_expectations(report: str, exp: dict):
    for s in exp.get("must_contain", []):
        assert s.lower() in report.lower(), f"Report missing phrase: {s!r}"
    for s in exp.get("must_not_contain", []):
        assert s.lower() not in report.lower(), f"Report should NOT contain: {s!r}"
    for pattern in exp.get("regex_must_match", []):
        assert re.search(pattern, report, flags=re.I | re.M), f"Regex not found: {pattern!r}"

def log_judgment_pretty(cid: str, judgment, overall_threshold: int, per_crit: dict) -> None:
    # Compute status
    pass_overall = judgment.score >= overall_threshold
    pass_per_crit = all(judgment.criteria_scores.get(k, 0) >= th for k, th in per_crit.items())
    status = "PASS ✅" if (pass_overall and pass_per_crit) else "FAIL ❌"

    # Table width for criteria
    crit_names = list(judgment.criteria_scores.keys() or [])
    width = max([len(c) for c in crit_names] + [8])

    lines = []
    lines.append("\n╔════════════════════════════════════════════════════════════╗")
    lines.append(f"║ Case: {cid}")
    lines.append(f"║ Status: {status}")
    lines.append(f"║ Overall: {judgment.score:>3} (threshold ≥{overall_threshold})")
    lines.append("╠════════════════════════════════════════════════════════════╣")
    lines.append("║ Criteria scores:")

    for crit in sorted(judgment.criteria_scores.keys()):
        val = judgment.criteria_scores.get(crit, 0)
        th = per_crit.get(crit)
        th_txt = f"  (≥{th})" if th is not None else ""
        ok_txt = "" if th is None else ("  ✓" if val >= th else "  ✗")
        lines.append(f"║   • {crit:<{width}} : {val:>3}{th_txt}{ok_txt}")

    if judgment.issues:
        lines.append("╠════════ Issues ────────────────────────────────────────────╣")
        for i in judgment.issues:
            lines.append(f"║   • {i}")

    if judgment.suggestions:
        lines.append("╠════════ Suggestions ───────────────────────────────────────╣")
        for s in judgment.suggestions:
            lines.append(f"║   • {s}")

    lines.append("╚════════════════════════════════════════════════════════════╝")
    logger.info("\n".join(lines))

@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
async def test_yaml_case(case):
    cid = case["id"]
    q = case["query"]
    attachments = case.get("attachments", [])
    timeout_s = case.get("timeout_s", 240)
    exp = case.get("expect", {})
    judge_cfg = case.get("judge", {})

    # 1) Run agent
    try:
        run_res = await asyncio.wait_for(
            run_question_with_orchestrator(q, attachments=attachments),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError:
        pytest.fail(f"[{cid}] timed out after {timeout_s}s")

    report = run_res.answer_markdown
    
    reports_dir = REPO_ROOT / "eval" / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_file = reports_dir / f"{cid}_report.md"
    report_file.write_text(report)
    logger.info(f"Report saved to: {report_file}")

    # 2) Hard expectations (pre-judge)
    _assert_text_expectations(report, exp)

    # 3) Build rubric override if provided (global -> case override)
    rubric_override = None
    if RUBRIC_YAML:
        rubric_override = [RubricCriterion(**r) for r in RUBRIC_YAML]
    if judge_cfg.get("rubric"):
        rubric_override = [RubricCriterion(**r) for r in judge_cfg["rubric"]]

    # 4) Judge the answer
    judgment = await judge_answer(
        question=q,
        answer_markdown=report,
        judge_request=judge_cfg.get("request", "Judge for correctness and usefulness."),
        rubric=rubric_override,
        system_append=judge_cfg.get("system_append", ""),
    )
    logger.info("[%s] score=%d criteria=%s",
                cid, judgment.score, judgment.criteria_scores)

    # 5) Assertions from judge
    
    overall_threshold = judge_cfg.get("overall_threshold", 70)
    per_crit = judge_cfg.get("per_criterion_thresholds", {})
    
    # Pretty block log
    log_judgment_pretty(cid, judgment, overall_threshold, per_crit)
    
    
    message = (
        f"[{cid}] overall score {judgment.score} < {overall_threshold}\n"
        f"Issues: {judgment.issues}\nSuggestions: {judgment.suggestions}"
    )
    assert judgment.score >= overall_threshold, message

    
    for crit, th in per_crit.items():
        got = judgment.criteria_scores.get(crit, 0)
        per_crit_message = f"[{cid}] criterion '{crit}' {got} < {th}"
        assert got >= th, per_crit_message

