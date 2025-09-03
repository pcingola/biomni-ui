from __future__ import annotations
import os, time
from dataclasses import dataclass

from aixtools.agents import get_agent

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from biomni_ui.agents import BiomniAgentOrchestrator
from biomni_ui.file_manager import FileManager
from biomni_ui.session_manager import session_manager

# ─────────────────────────────────────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────────────────────────────────────

class RubricCriterion(BaseModel):
    name: str
    weight: float = Field(..., gt=0)
    description: str

class Judgment(BaseModel):
    score: int = Field(..., ge=0, le=100)                # overall 0–100
    pass_fail: bool
    reasoning: str
    criteria_scores: dict[str, int]                      # each 0–100
    issues: list[str] = []
    suggestions: list[str] = []

# ─────────────────────────────────────────────────────────────────────────────

def _rubric_md(rubric: list[RubricCriterion]) -> str:
    return "\n".join([f"- **{c.name}** (w={c.weight}): {c.description}" for c in rubric])

def build_judge_agent(rubric: list[RubricCriterion], system_append: str = "") -> Agent:
    """Builds a judge agent with the given rubric and system instructions."""

    system_prompt = f"""
        You are an impartial evaluator (LLM-as-a-Judge). Return ONLY JSON matching the `Judgment` schema.
        Compute an overall 0-100 score using the weighted criteria below.

        Rubric:
        {_rubric_md(rubric)}

        Rules:
        - Be strict but fair; penalize hallucinations and vague methods.
        - Provide 2-6 specific, actionable suggestions.
        {system_append}
        """

    return get_agent(system_prompt=system_prompt, output_type=Judgment)

# ─────────────────────────────────────────────────────────────────────────────
# Runner utilities
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RunResult:
    question: str
    answer_markdown: str
    elements: list
    duration_s: float

async def run_question_with_orchestrator(
    question: str,
    *,
    attachments: list[str] | None = None
) -> RunResult:
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

    t0 = time.time()
    res = await orch.run_full_pipeline(
        query=enhanced_query,
        session_id=session_id,
        session_outputs_dir=str(session_out),
        history=[],
        progress=progress_cb,
    )
    t1 = time.time()

    return RunResult(
        question=question,
        answer_markdown=res["report_md"],
        elements=res["elements"],
        duration_s=(t1 - t0),
    )

async def judge_answer(
    *,
    question: str,
    answer_markdown: str,
    judge_request: str,
    rubric: list[RubricCriterion],
    system_append: str = ""
) -> Judgment:
    judge: Agent = build_judge_agent(rubric=rubric, system_append=system_append)

    user_prompt = f"""
    User question:
    {question}
    Assistant answer (Markdown):
    {answer_markdown}
    Evaluation request (instructions for the judge):
    {judge_request}
    Return ONLY valid JSON for the Judgment schema.
    """.strip()

    result = await judge.run(user_prompt)
    return result.output