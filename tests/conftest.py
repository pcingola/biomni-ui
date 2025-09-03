import yaml
import pathlib
import pytest
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "eval" / "cases"
RUBRIC_FILE = ROOT / "eval" / "rubric.yaml"

def _load_cases():
    cases = []
    for yf in sorted(CASES_DIR.glob("*.yaml")):
        with open(yf, "r") as fh:
            cases.append(yaml.safe_load(fh))
    return cases

def _load_rubric():
    if RUBRIC_FILE.exists():
        data = yaml.safe_load(RUBRIC_FILE.read_text())
        return data.get("rubric")
    return None

@pytest.fixture(scope="session")
def rubric_yaml():
    return _load_rubric()

@pytest.fixture(scope="session")
def cases():
    loaded = _load_cases()
    assert loaded, f"No YAML cases found in {CASES_DIR}"
    return loaded

@pytest.fixture(autouse=True)
def no_chainlit_elements(monkeypatch):
    def _noop(*args, **kwargs):
        return []
    # Patch the bound name used by agents.py
    monkeypatch.setattr("biomni_ui.agents.gather_execution_elements", _noop, raising=False)
    monkeypatch.setattr("biomni_ui.utils.gather_execution_elements", _noop, raising=False)
    
@pytest.fixture(autouse=True)
def stub_chainlit_elements(monkeypatch):
    class _Dummy:
        def __init__(self, *a, **k): pass
    # When code does `import chainlit as cl; cl.File(...)`
    monkeypatch.setattr("chainlit.File", _Dummy, raising=False)
    monkeypatch.setattr("chainlit.Image", _Dummy, raising=False)
    monkeypatch.setattr("chainlit.Text", _Dummy, raising=False)