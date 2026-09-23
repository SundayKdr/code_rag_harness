import asyncio
from pathlib import Path


class GitError(RuntimeError):
    pass


async def run_git(
    *args: str,
    cwd: Path | None = None,
) -> str:

    cmd = ["git", *args]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise GitError(
            f"git command failed: {' '.join(cmd)}\n"
            f"{stderr.decode().strip()}"
        )

    return stdout.decode().strip()
