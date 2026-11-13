"""Bounded, cancellable subprocesses running directly on the operator's host."""

import asyncio
import os
import signal
from .config import ConfigError


async def run_process(argv, cwd=None, timeout=60, output_limit=128000, stdin=None):
    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        stdin=asyncio.subprocess.PIPE
        if stdin is not None
        else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=os.name != "nt",
    )

    async def read(stream):
        raw = bytearray()
        while chunk := await stream.read(16384):
            raw.extend(chunk)
            if len(raw) > output_limit:
                raise ConfigError("Process output exceeded its configured limit.")
        return bytes(raw)

    async def feed():
        if stdin is not None:
            try:
                process.stdin.write(stdin)
                await process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                process.stdin.close()

    tasks = [
        asyncio.create_task(read(process.stdout)),
        asyncio.create_task(read(process.stderr)),
        asyncio.create_task(feed()),
    ]
    try:
        async with asyncio.timeout(timeout):
            stdout, stderr, _ = await asyncio.gather(*tasks)
            await process.wait()
    except BaseException:
        if process.returncode is None:
            try:
                if os.name != "nt":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    # taskkill also terminates descendants; no shell interpolation.
                    killer = await asyncio.create_subprocess_exec(
                        "taskkill",
                        "/PID",
                        str(process.pid),
                        "/T",
                        "/F",
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await killer.wait()
                    if process.returncode is None:
                        process.kill()
            except ProcessLookupError:
                pass
            finally:
                await process.wait()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    return {
        "returncode": process.returncode,
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace"),
        "execution": "direct_host",
    }
