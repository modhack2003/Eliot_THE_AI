"""Typed evidence tools. Model text never becomes an executable shell command."""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import os
from pathlib import Path
import re
import shutil
import signal
import tempfile
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .config import ConfigError


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListFiles(Input):
    path: str = "."


class ReadFile(Input):
    path: str
    start_line: int = Field(default=1, ge=1)
    limit: int = Field(default=120, ge=1, le=200)


class SearchFiles(Input):
    text: str = Field(min_length=1, max_length=200)


class FileInfo(Input):
    path: str


class Artifact(Input):
    path: str = Field(min_length=1, max_length=200)
    content: str = Field(max_length=100_000)


class ReadSkill(Input):
    skill_id: str
    resource: str = "SKILL.md"
    start_line: int = Field(default=1, ge=1)
    limit: int = Field(default=120, ge=1, le=200)


class HttpObserve(Input):
    url: str = Field(max_length=2048)


class NmapServices(Input):
    host: str
    ports: list[int] = Field(min_length=1, max_length=128)


MODELS = {"list_files": ListFiles, "read_file": ReadFile, "read_artifact": ReadFile, "search_files": SearchFiles, "file_info": FileInfo, "write_artifact": Artifact, "read_skill": ReadSkill, "http_observe": HttpObserve, "nmap_services": NmapServices}
DESCRIPTIONS = {
    "list_files": "List up to 500 evidence files beneath a workspace directory.",
    "read_file": "Read a page of an evidence text file, with source line numbers.",
    "read_artifact": "Read a report/artifact produced by this task graph, using its workspace-relative .eliot-artifacts path.",
    "search_files": "Find a literal string in up to 500 text files; no regex execution.",
    "file_info": "Inspect size, SHA256, magic bytes and printable strings of a file up to 8MB.",
    "write_artifact": "Write a new task artifact. Existing different content cannot be overwritten.",
    "read_skill": "Read a pinned Markdown skill or reference page. It supplies guidance, not tools.",
    "http_observe": "One unauthenticated GET to an explicitly scoped host. Redirects are not followed.",
    "nmap_services": "Kali/Linux TCP connect and light service discovery on one explicitly scoped host and up to 128 ports. No vulnerability scripts or exploit execution.",
}
DENIED = {".git", ".ssh", ".aws", ".azure", ".config", "__pycache__", ".venv", "node_modules", ".eliot-artifacts"}


def normalize_host(host):
    if not isinstance(host, str) or len(host) > 253:
        raise ConfigError("Scope entries must be exact host names or IP addresses.")
    host = host.strip().lower().rstrip(".")
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        if not re.fullmatch(r"(?=.{1,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host) or ".." in host:
            raise ConfigError("Use exact host names/IPs in scope; URLs, wildcards and CIDRs are not supported.")
        return host


class Tools:
    def __init__(self, catalog, http_transport=None, task_graph=None):
        self.catalog = catalog
        self.http_transport = http_transport
        self.task_graph = task_graph

    def schemas(self, mission):
        return [{"name": name, "description": DESCRIPTIONS[name], "input_schema": MODELS[name].model_json_schema()} for name in MODELS if mission["policy"]["network"] or name not in {"http_observe", "nmap_services"}]

    def path(self, mission, relative):
        root = Path(mission["workspace"]).resolve()
        supplied = Path(relative)
        if supplied.is_absolute() or any(part in DENIED or part.startswith(".env") or part.endswith((".pem", ".key")) for part in supplied.parts):
            raise ConfigError("Choose an evidence path inside the task workspace, outside secret/configuration directories.")
        path = (root / supplied).resolve()
        if not path.is_relative_to(root):
            raise ConfigError("The requested path leaves the task workspace.")
        if any(part in DENIED or part.startswith(".env") or part.endswith((".pem", ".key")) for part in path.relative_to(root).parts):
            raise ConfigError("That path is excluded from task evidence.")
        return path

    def files(self, mission, base="."):
        root = self.path(mission, base)
        if not root.is_dir():
            raise ConfigError("Evidence directory not found.")
        found = []
        # Walk without following directory symlinks; never traverse excluded trees.
        for directory, names, files in os.walk(root, followlinks=False):
            names[:] = sorted(n for n in names if n not in DENIED and not n.startswith(".env") and not (Path(directory)/n).is_symlink())
            for name in sorted(files):
                path = Path(directory) / name
                rel = path.relative_to(Path(mission["workspace"]))
                try:
                    self.path(mission, str(rel))
                except ConfigError:
                    continue
                if path.is_symlink():
                    continue
                found.append(path)
                if len(found) >= 500:
                    return found
        return found

    def scoped(self, mission, host):
        if not mission["policy"]["network"] or normalize_host(host) not in mission["policy"]["targets"]:
            raise ConfigError("Network action denied: this exact host is not enabled in the task scope.")

    async def execute(self, mission, name, arguments):
        if name not in MODELS:
            raise ConfigError("Tool is not registered.")
        args = MODELS[name].model_validate(arguments).model_dump()
        if name == "http_observe":
            return await self.http_observe(mission, **args)
        if name == "nmap_services":
            return await self.nmap_services(mission, **args)
        return await asyncio.to_thread(self.local, mission, name, args)

    def local(self, mission, name, args):
        if name == "read_skill":
            return self.catalog.read(**args)
        if name == "list_files":
            paths = self.files(mission, args["path"])
            return {"files": [str(p.relative_to(mission["workspace"])) for p in paths], "limit": 500, "at_limit": len(paths) == 500}
        if name == "search_files":
            matches = []
            for path in self.files(mission):
                if path.stat().st_size > 1_000_000:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except (UnicodeError, OSError):
                    continue
                for line_no, line in enumerate(text.splitlines(), 1):
                    if args["text"].lower() in line.lower():
                        matches.append({"path": str(path.relative_to(mission["workspace"])), "line": line_no, "text": line[:500]})
                        if len(matches) >= 40:
                            return {"matches": matches, "at_limit": True}
            return {"matches": matches, "at_limit": False}
        if name == "write_artifact":
            root = Path(mission["workspace"]).resolve()
            artifact_root = (root / ".eliot-artifacts" / mission["id"]).resolve()
            path = (artifact_root / args["path"]).resolve()
            if not artifact_root.is_relative_to(root) or not path.is_relative_to(artifact_root) or Path(args["path"]).is_absolute():
                raise ConfigError("Artifacts must stay inside this task's artifact directory.")
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = args["content"].encode("utf-8")
            descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".eliot-write-")
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                try:
                    os.link(temporary, path)
                except FileExistsError:
                    if path.is_symlink() or path.read_bytes() != raw:
                        raise ConfigError("That artifact already exists with different content. Choose a new filename.") from None
            finally:
                os.unlink(temporary)
            return {"path": str(path.relative_to(root)), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        if name == "read_artifact":
            root = Path(mission["workspace"]).resolve()
            path = (root / args["path"]).resolve()
            owners = [m["id"] for m in self.task_graph(mission["root_id"])] if self.task_graph else [mission["id"]]
            if not any(path.is_relative_to((root/".eliot-artifacts"/owner).resolve()) and (root/".eliot-artifacts"/owner).resolve().is_relative_to(root) for owner in owners):
                raise ConfigError("The artifact does not belong to this task graph.")
        else:
            path = self.path(mission, args["path"])
        if not path.is_file():
            raise ConfigError("Evidence file not found.")
        maximum = 8_000_000 if name == "file_info" else 1_000_000
        if path.stat().st_size > maximum:
            raise ConfigError("The evidence file exceeds this tool's input-size limit.")
        raw = path.read_bytes()
        if name == "file_info":
            return {"path": args["path"], "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "header_hex": raw[:64].hex(), "printable_strings": [m.decode("ascii") for m in re.findall(rb"[ -~]{8,128}", raw)[:80]], "truncated_strings": True}
        lines = raw.decode("utf-8").splitlines()
        text = "\n".join(f"{i}: {lines[i-1]}" for i in range(args["start_line"], min(len(lines)+1, args["start_line"]+args["limit"])))
        return {"path": args["path"], "text": text[:12_000], "total_lines": len(lines), "start_line": args["start_line"], "truncated": len(text) > 12_000}

    async def http_observe(self, mission, url):
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ConfigError("Use an HTTP(S) URL without embedded credentials or fragments.")
        self.scoped(mission, parsed.hostname)
        async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False, transport=self.http_transport) as client:
            async with client.stream("GET", url, headers={"User-Agent": "Eliot-Authorized-Observation/2"}) as response:
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk[:max(0, 128_000-len(raw))])
                    if len(raw) >= 128_000:
                        break
                return {"url": url, "status": response.status_code, "headers": {key: response.headers[key][:500] for key in ["content-type", "server", "location"] if key in response.headers}, "text": bytes(raw).decode("utf-8", errors="replace")[:12_000], "sample_sha256": hashlib.sha256(raw).hexdigest(), "sample_limited": len(raw) >= 128_000, "redirect_followed": False}

    async def nmap_services(self, mission, host, ports):
        self.scoped(mission, host)
        host = normalize_host(host)
        if not all(type(port) is int and 1 <= port <= 65535 for port in ports):
            raise ConfigError("TCP ports must be integers between 1 and 65535.")
        executable = shutil.which("nmap")
        if not executable:
            raise ConfigError("nmap is not installed in this worker environment.")
        family = ["-6"] if ":" in host else []
        process = await asyncio.create_subprocess_exec(executable, *family, "-sT", "-sV", "--version-light", "-Pn", "-n", "--host-timeout", "30s", "--max-retries", "1", "-p", ",".join(map(str, sorted(set(ports)))), "-oX", "-", host, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, start_new_session=os.name != "nt")
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), 40)
        except BaseException:
            if process.returncode is None:
                try:
                    if os.name != "nt":
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                except ProcessLookupError:
                    pass
                await process.wait()
            raise
        if process.returncode != 0:
            raise ConfigError("nmap did not complete successfully.")
        if len(stdout) > 1_000_000:
            raise ConfigError("nmap output exceeded the result limit.")
        tree = ET.fromstring(stdout)
        observations = [{"port": p.get("portid"), "state": p.find("state").get("state") if p.find("state") is not None else "unknown", "service": dict(p.find("service").attrib) if p.find("service") is not None else {}} for p in tree.findall(".//port")]
        return {"host": host, "observations": observations, "xml_sha256": hashlib.sha256(stdout).hexdigest(), "note": "Service observations are not verified vulnerabilities."}
