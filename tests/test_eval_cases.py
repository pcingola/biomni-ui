"""Custom runner for eval LLM orchestrator."""

import asyncio
import time
import os
import pathlib
from typing import Any
import pytest
import yaml

from biomni_ui.agents import BiomniAgentOrchestrator
from biomni_ui.file_manager import FileManager
from biomni_ui.session_manager import session_manager

from pondera.runner.base import Runner, ProgressCallback
from pondera.models.run import RunResult
from pondera.api import evaluate_case_async
from pondera.judge.base import Judge

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "eval" / "cases"

def _load_cases():
    cases = []
    for yf in sorted(CASES_DIR.glob("*.yaml")):
        case = yaml.safe_load(yf.read_text())
        if "id" not in case:
            case["id"] = yf.stem
        case["path"] = str(yf)
        cases.append(case)

    # Optional filter: EVAL_CASE="id1,id2" or any substring match
    flt = os.getenv("EVAL_CASE")
    if flt:
        needles = [s.strip() for s in flt.split(",") if s.strip()]
        cases = [c for c in cases if any(n in c["id"] for n in needles)]
    return cases

CASES = _load_cases()
if not CASES:
    raise RuntimeError(f"No YAML cases found in {CASES_DIR}")
class EvalBiomniRunner(Runner):
    """Runner that uses the eval LLM orchestrator."""

    async def run(
        self,
        question: str,
        attachments: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        progress: ProgressCallback | None = None,
    ) -> RunResult:
        """Run the eval LLM orchestrator."""
        # Convert attachments dict to list format expected by orchestrator
        attachment_list = []
        if attachments:
            for name, content in attachments.items():
                attachment_list.append({"name": name, "content": content})

        fm = FileManager()
        orch = BiomniAgentOrchestrator(file_manager=fm)
        session_id = session_manager.create_session()
        session_out = session_manager.get_session_outputs_path(session_id)

        enhanced_query = question
        if attachments:
            for path in attachments:
                with open(path, "rb") as fh:
                    data = fh.read()
                    enhanced_query += f"\n{path}\n{data}\n"

        async def progress_cb(_line: str):  # keep quiet in tests; could print if debugging
            return

        res = await orch.run_full_pipeline(
            query=enhanced_query,
            session_id=session_id,
            session_outputs_dir=str(session_out),
            history=[],
            progress=progress_cb,
        )

        return RunResult(
            question=question,
            answer=res["report_md"],
            files=res["elements"],
        )
        
@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
async def test_yaml_case(case):

    res = await evaluate_case_async(case["path"], runner=EvalBiomniRunner(), judge=Judge(), artifacts_root="eval/artifacts")
    assert res.passed, f"Case {case['id']} failed"
