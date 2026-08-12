from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import py_compile
import subprocess
import sys

@dataclass
class CheckResult:
    name: str
    success: bool
    output: str

class SafePythonRunner:
    def __init__(self, workspace: str | Path):
        self.root = Path(workspace).expanduser().resolve()

    def compile_files(self, relative_paths: list[str]) -> list[CheckResult]:
        results = []
        for rel in relative_paths:
            if not rel.lower().endswith(".py"):
                continue
            path = (self.root / rel).resolve()
            try:
                path.relative_to(self.root)
            except ValueError:
                results.append(CheckResult(f"compile:{rel}", False, "Path outside workspace"))
                continue
            try:
                py_compile.compile(str(path), doraise=True)
                results.append(CheckResult(f"compile:{rel}", True, "Syntax compile passed"))
            except Exception as exc:
                results.append(CheckResult(f"compile:{rel}", False, str(exc)))
        return results

    def run_unittests(self, timeout: int = 20) -> CheckResult:
        if not (self.root / "tests").exists():
            return CheckResult("unittest", True, "No tests directory; tests not run")
        try:
            cp = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            return CheckResult("unittest", False, f"Tests exceeded {timeout}s")
        output = ((cp.stdout or "") + "\n" + (cp.stderr or "")).strip()
        return CheckResult("unittest", cp.returncode == 0, output or "Tests completed")
