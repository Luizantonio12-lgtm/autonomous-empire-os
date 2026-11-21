import asyncio
import os
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

DEPLOYMENTS_ROOT = Path(__file__).resolve().parents[2] / "deployments"
DEPLOYMENTS_ROOT.mkdir(parents=True, exist_ok=True)


@dataclass
class SandboxResult:
    project_id: str
    workspace_dir: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    files_written: list[str]
    compute_cost_usd: float


class IsolatedSandboxExecutor:
    """
    Motor de Execução Isolada Nível 2 para a Fábrica de Software.
    - Executa isolamento por processo com scrubbing de segredos
    - Corre bateria Python unittest + AST + Node.js syntax check (node --check)
    - Inicializa repositório Git real versionado e gera artefacto .zip para download/deploy
    """

    COST_PER_SECOND_USD = 0.00028

    async def build_and_verify(
        self,
        project_id: str,
        files: dict[str, str],
        verification_script: str,
        timeout_seconds: int = 25,
    ) -> SandboxResult:
        project_dir = DEPLOYMENTS_ROOT / project_id
        project_dir.mkdir(parents=True, exist_ok=True)

        written_files: list[str] = []
        for rel_path, content in files.items():
            safe_rel = Path(rel_path)
            if safe_rel.is_absolute() or ".." in safe_rel.parts:
                raise ValueError(f"Caminho inseguro bloqueado pela Sandbox: {rel_path}")
            target = project_dir / safe_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written_files.append(rel_path)

        qa_file = project_dir / "_sandbox_qa_runner.py"
        qa_file.write_text(verification_script, encoding="utf-8")

        clean_env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": str(project_dir),
            "PYTHONDONTWRITEBYTECODE": "1",
            "SANDBOX_MODE": "ISOLATED_L2",
        }

        t0 = time.perf_counter()
        proc = await asyncio.create_subprocess_exec(
            "python3",
            str(qa_file),
            cwd=str(project_dir),
            env=clean_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_seconds
            )
            exit_code = proc.returncode if proc.returncode is not None else 1
            stdout_str = stdout_b.decode("utf-8", errors="replace")
            stderr_str = stderr_b.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            proc.kill()
            exit_code = 124
            stdout_str = ""
            stderr_str = f"Sandbox Timeout excedido ({timeout_seconds}s)."

        duration_ms = max(1, int((time.perf_counter() - t0) * 1000))
        compute_cost = round(max(0.0005, (duration_ms / 1000.0) * self.COST_PER_SECOND_USD), 6)

        return SandboxResult(
            project_id=project_id,
            workspace_dir=str(project_dir),
            exit_code=exit_code,
            stdout=stdout_str.strip(),
            stderr=stderr_str.strip(),
            duration_ms=duration_ms,
            files_written=written_files,
            compute_cost_usd=compute_cost,
        )

    async def finalize_git_and_archive(
        self,
        project_id: str,
        commit_message: str,
    ) -> tuple[str, Path]:
        project_dir = DEPLOYMENTS_ROOT / project_id
        qa_runner = project_dir / "_sandbox_qa_runner.py"
        if qa_runner.exists():
            qa_runner.unlink()

        git_cmds = [
            ["git", "init", "-q"],
            ["git", "config", "user.name", "Autonomous Software Factory"],
            ["git", "config", "user.email", "factory@autonomous-empire.ai"],
            ["git", "add", "."],
            ["git", "commit", "-q", "-m", commit_message],
            ["git", "rev-parse", "--short", "HEAD"],
        ]

        commit_hash = "HEAD"
        for cmd in git_cmds:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(project_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, _ = await proc.communicate()
            if cmd[-1] == "HEAD" and proc.returncode == 0:
                commit_hash = out.decode("utf-8").strip()

        zip_path = DEPLOYMENTS_ROOT / f"{project_id}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(project_dir.rglob("*")):
                if file_path.is_file() and ".git" not in file_path.parts:
                    zf.write(file_path, arcname=str(file_path.relative_to(project_dir)))

        return commit_hash, zip_path


sandbox_executor = IsolatedSandboxExecutor()
