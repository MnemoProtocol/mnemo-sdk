"""Regression tests for the CI security token gate.

The gate is the bash step "No private implementation symbols in the public SDK"
in .github/workflows/ci.yml. These tests extract that step's script and run it
unchanged with the system grep against a scratch tree that has every scanned
path, with one probe line written into it. On the CI runners that grep is GNU
grep, the engine the gate itself uses.

BLOCKED probes must fail the gate; ALLOWED probes must pass it. Third-party
packages whose names end in _core (langchain_core, pydantic_core) are allowed;
the internal _core module and known internal compound identifiers are not.
"""

import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
STEP_NAME = "- name: No private implementation symbols in the public SDK"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("grep") is None,
    reason="the gate is a bash script that runs grep",
)


def gate_script() -> str:
    """The `run: |` block of the gate step, dedented, exactly as CI runs it."""
    lines = CI_YML.read_text(encoding="utf-8").splitlines()
    step = next(i for i, line in enumerate(lines) if line.strip() == STEP_NAME)
    run = next(i for i in range(step + 1, len(lines)) if lines[i].strip() == "run: |")
    indent = len(lines[run]) - len(lines[run].lstrip())
    body = []
    for line in lines[run + 1 :]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        body.append(line)
    return textwrap.dedent("\n".join(body)) + "\n"


def scanned_paths(script: str) -> list:
    match = re.search(r'grep -rnE "\$token" ([^;]+); then', script)
    assert match, "gate step no longer has the expected grep line"
    return match.group(1).split()


def run_gate(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-c", gate_script()], cwd=cwd, capture_output=True, text=True)


def gate_on_probe(tmp_path: Path, line: str) -> int:
    """Exit status of the gate on a tree whose only content is `line`."""
    for rel in scanned_paths(gate_script()):
        target = tmp_path / rel
        if rel.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
    (tmp_path / "mnemo_sdk" / "probe.py").write_text(line + "\n", encoding="utf-8")
    result = run_gate(tmp_path)
    assert result.returncode in (0, 1), result.stderr  # 2 would mean a grep error
    return result.returncode


BLOCKED = [
    # the internal _core module, in every import form
    "import _core",
    "from mnemo_sdk import _core",
    "import mnemo_sdk._core",
    "from . import _core",
    "from ._core import embed",
    'module = importlib.import_module("mnemo_sdk._core")',
    'name = "_core"',
    "import mnemo_core",
    # known internal compound identifiers
    "result = api._v1_verify_core(request)",
    "self._core_url = core_url",
    "response = self._core_client(credential)",
    "self._core_timeout = 5.0",
    "digest = hmac_sha256(key, canonical_core_bytes)",
    "outcome = real_core_verify(request)",
    "outcome = real_core_routed_verify(request)",
    "route = real_core_route(request)",
    "if subject_route_through_core_configured:",
    "t1_core_k = before",
    "assert duplicate_core_k_executions_zero",
    "monkeypatch.setattr(api, '_slow_core', slow)",
    "best = best_core_success",
    "run_core_trials(config)",
    'report["alignment_core"]',
]

ALLOWED = [
    "from langchain_core.documents import Document",
    "from langchain_core.vectorstores import InMemoryVectorStore",
    "import langchain_core",
    "import pydantic_core",
    "from pydantic_core import core_schema",
    "core = load()",
    "# the core idea of the example",
]


@pytest.mark.parametrize("line", BLOCKED)
def test_gate_blocks(tmp_path, line):
    assert gate_on_probe(tmp_path, line) == 1, line


@pytest.mark.parametrize("line", ALLOWED)
def test_gate_allows(tmp_path, line):
    assert gate_on_probe(tmp_path, line) == 0, line


def test_gate_passes_on_this_repository():
    # The repository itself (including examples/ with its langchain_core
    # imports) must pass, as it does in the CI security job.
    result = run_gate(REPO_ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
