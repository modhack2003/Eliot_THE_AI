"""Typed evidence tools. Model text never becomes an executable shell command."""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import os
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit
from defusedxml import ElementTree as ET

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .config import ConfigError
from . import operations, device_tools
from . import filesystem
from .processes import run_process
from .knowledge import Knowledge
from .policy import active, network_scope


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListFiles(Input):
    path: str = "."
    offset: int = Field(default=0,ge=0)
    limit: int = Field(default=500,ge=1,le=500)


class ReadFile(Input):
    path: str
    start_line: int = Field(default=1, ge=1)
    limit: int = Field(default=120, ge=1, le=200)
    character_offset: int = Field(default=0,ge=0)


class SearchFiles(Input):
    text: str = Field(min_length=1, max_length=200)
    file_offset: int = Field(default=0,ge=0)
    start_line: int = Field(default=1,ge=1)


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
    refresh: bool = False


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
    def __init__(self, catalog, http_transport=None, task_graph=None, mission_store=None):
        self.catalog = catalog
        self.http_transport = http_transport
        self.task_graph = task_graph
        self.mission_store = mission_store
        self.knowledge = Knowledge(mission_store.store) if mission_store else None
        self.edit_lock = asyncio.Lock()
        self.devices = device_tools.DeviceTools(self)

    def schemas(self, mission):
        return [{"name": name, "description": DESCRIPTIONS[name], "input_schema": MODELS[name].model_json_schema()} for name in MODELS if mission["policy"]["network"] or name not in {"http_observe", "nmap_services"}] + [{"name":name,"description":operations.DESCRIPTIONS[name],"input_schema":model.model_json_schema(),"effect":operations.EFFECTS.get(name,"read"),"execution":"direct_host"} for name,model in operations.MODELS.items() if operations.allowed(mission,name)] + [{"name":name,"description":device_tools.DESCRIPTIONS[name],"input_schema":model.model_json_schema(),"execution":"direct_host"} for name,model in device_tools.MODELS.items() if device_tools.allowed(mission,name)]

    def registry(self):
        import importlib.util
        records=[]
        models={**MODELS,**operations.MODELS,**device_tools.MODELS}
        descriptions={**DESCRIPTIONS,**operations.DESCRIPTIONS,**device_tools.DESCRIPTIONS}
        permissions={'run_command':'host_execution','run_python':'host_execution','edit_file':'file_edit','rollback_file':'file_edit','browser_action':'browser','desktop_action':'desktop','robot_action':'robotics','http_observe':'network','nmap_services':'network'}
        for name,model in models.items():
            dependency='playwright' if name=='browser_action' else 'pyautogui' if name=='desktop_action' else None
            available=importlib.util.find_spec(dependency) is not None if dependency else bool(shutil.which('nmap')) if name=='nmap_services' else True
            records.append({'name':name,'description':descriptions[name],'input_schema':model.model_json_schema(),'output_schema':{'type':'object'},'effect':operations.EFFECTS.get(name,'device_action' if name in device_tools.MODELS and name!='inspect_image' else 'artifact_write' if name=='write_artifact' else 'read'),'available':available,'dependency':dependency,'required_permission':permissions.get(name),'execution':'direct_host','timeout_seconds':60,'retry':'Explicit new attempt after inspected failure; committed checkpoints replay recorded results.','verification':'Inspect recorded tool output and operator completion checks.'})
        return records

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

    def artifact_path(self, mission, relative, owner=None):
        root = Path(mission["workspace"]).resolve()
        supplied = Path(relative)
        if supplied.is_absolute() or ".." in supplied.parts:
            raise ConfigError("Artifacts must stay inside this task's artifact directory.")
        artifact_root = root / ".eliot-artifacts" / (owner or mission["id"])
        path = artifact_root / supplied
        for candidate in [root / ".eliot-artifacts", artifact_root, *path.parents, path]:
            if candidate == root or not candidate.is_relative_to(root):
                continue
            if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
                raise ConfigError("Artifact paths cannot contain symlinks or junctions.")
        if not path.resolve().is_relative_to(artifact_root):
            raise ConfigError("Artifacts must stay inside this task's artifact directory.")
        if any(part.startswith(".env") or part.endswith((".pem", ".key")) or part in DENIED - {".eliot-artifacts"} for part in supplied.parts):
            raise ConfigError("That path is excluded from task evidence.")
        return path

    def revision(self, mission, name, arguments):
        """Version observation inputs, separately from replaying a committed step."""
        if name in {"read_file", "file_info"}:
            try:
                path = self.path(mission, arguments.get("path", ""))
                stat = path.stat()
                return [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]
            except (OSError, ConfigError):
                return "unavailable"
        if name in {"list_files", "search_files"}:
            try:
                return [(str(p.relative_to(mission["workspace"])), p.stat().st_size, p.stat().st_mtime_ns) for p in self.files(mission, arguments.get("path", "."), arguments.get("offset",arguments.get("file_offset",0)), arguments.get("limit",500)+1)]
            except (OSError, ConfigError):
                return "unavailable"
        return None

    def files(self, mission, base=".", offset=0, limit=500):
        root = self.path(mission, base)
        if not root.is_dir():
            raise ConfigError("Evidence directory not found.")
        found = []
        skipped = 0
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
                if skipped < offset:
                    skipped += 1
                    continue
                found.append(path)
                if len(found) >= limit:
                    return found
        return found

    def scoped(self, mission, host, port=None, path=None):
        network_scope(mission["policy"],normalize_host(host),port,path)

    async def execute(self, mission, name, arguments):
        active(mission['policy'])
        if name in device_tools.MODELS:
            return await self.devices.execute(mission,name,device_tools.MODELS[name].model_validate(arguments).model_dump())
        if name in operations.MODELS:
            args = operations.MODELS[name].model_validate(arguments).model_dump()
            if operations.EFFECTS.get(name) in {'workspace_write','memory_write'}:
                return await operations.execute(self, mission, name, args)
            async with asyncio.timeout(mission['policy'].get('tool_timeout', 60) + 5):
                return await operations.execute(self, mission, name, args)
        if name not in MODELS:
            raise ConfigError("Tool is not registered.")
        args = MODELS[name].model_validate(arguments).model_dump()
        if name == "http_observe":
            return await self.http_observe(mission, **args)
        if name == "nmap_services":
            return await self.nmap_services(mission, **args)
        # Atomic local writes settle before cancellation is acknowledged. The runtime
        # shields and journals writes; read-only thread results may be discarded.
        return await asyncio.to_thread(self.local, mission, name, args)

    def local(self, mission, name, args):
        if name == "read_skill":
            return self.catalog.read(**args)
        if name == "list_files":
            paths = self.files(mission, args["path"], args.get('offset',0), args.get('limit',500)+1)
            limit=args.get('limit',500)
            return {"files":[str(p.relative_to(mission["workspace"])) for p in paths[:limit]],"limit":limit,"at_limit":len(paths)>limit,"next_offset":args.get('offset',0)+limit if len(paths)>limit else None}
        if name == "search_files":
            matches = []
            paths=self.files(mission,offset=args.get("file_offset",0),limit=501)
            for index,path in enumerate(paths[:500]):
                if path.stat().st_size > 1_000_000:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except (UnicodeError, OSError):
                    continue
                for line_no, line in enumerate(text.splitlines(), 1):
                    if index==0 and line_no<args.get("start_line",1):
                        continue
                    if args["text"].lower() in line.lower():
                        matches.append({"path": str(path.relative_to(mission["workspace"])), "line": line_no, "text": line[:500]})
                        if len(matches) >= 40:
                            return {"matches":matches,"at_limit":True,"next_file_offset":args.get("file_offset",0)+index,"next_line":line_no+1}
            return {"matches":matches,"at_limit":len(paths)>500,"next_file_offset":args.get("file_offset",0)+500 if len(paths)>500 else None,"next_line":1}
        if name == "write_artifact":
            root = Path(mission["workspace"]).resolve()
            path = self.artifact_path(mission, args["path"])
            raw=args['content'].encode('utf-8')
            filesystem.write_artifact(root,path.relative_to(root),raw)
            return {"path": str(path.relative_to(root)), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        if name == "read_artifact":
            root = Path(mission["workspace"]).resolve()
            supplied = Path(args["path"])
            owners = [m["id"] for m in self.task_graph(mission["root_id"])] if self.task_graph else [mission["id"]]
            if supplied.is_absolute() or len(supplied.parts) < 3 or supplied.parts[0] != ".eliot-artifacts" or supplied.parts[1] not in owners:
                raise ConfigError("The artifact does not belong to this task graph.")
            path = self.artifact_path(mission, Path(*supplied.parts[2:]), supplied.parts[1])
        else:
            path = self.path(mission, args["path"])
        if not path.is_file():
            raise ConfigError("Evidence file not found.")
        maximum = 8_000_000 if name == "file_info" else 1_000_000
        if path.stat().st_size > maximum:
            raise ConfigError("The evidence file exceeds this tool's input-size limit.")
        raw = filesystem.read_artifact(root,path.relative_to(root),maximum) if name=="read_artifact" else path.read_bytes()
        if name == "file_info":
            return {"path": args["path"], "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "header_hex": raw[:64].hex(), "printable_strings": [m.decode("ascii") for m in re.findall(rb"[ -~]{8,128}", raw)[:80]], "truncated_strings": True}
        lines = raw.decode("utf-8").splitlines()
        text = "\n".join(f"{i}: {lines[i-1]}" for i in range(args["start_line"], min(len(lines)+1, args["start_line"]+args["limit"])))
        offset=args.get('character_offset',0)
        end=offset+12000
        return {"path":args["path"],"text":text[offset:end],"total_lines":len(lines),"start_line":args["start_line"],"end_line":min(len(lines),args['start_line']+args['limit']-1),"truncated":end<len(text),"next_character_offset":end if end<len(text) else None,"next_start_line":args['start_line']+args['limit'] if args['start_line']+args['limit']<=len(lines) else None,"sha256":hashlib.sha256(raw).hexdigest(),"provenance":"workspace_source"}

    async def http_observe(self, mission, url, refresh=False):
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ConfigError("Use an HTTP(S) URL without embedded credentials or fragments.")
        self.scoped(mission, parsed.hostname, parsed.port or (443 if parsed.scheme=="https" else 80), parsed.path or "/")
        async with asyncio.timeout(30), httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False, transport=self.http_transport) as client:
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
        for port in ports:
            self.scoped(mission,host,port)
        executable = shutil.which("nmap")
        if not executable:
            raise ConfigError("nmap is not installed in this worker environment.")
        family = ["-6"] if ":" in host else []
        result=await run_process([executable,*family,"-sT","-sV","--version-light","-Pn","-n","--host-timeout","30s","--max-retries","1","-p",",".join(map(str,sorted(set(ports)))),"-oX","-",host],timeout=40,output_limit=1000000)
        if result['returncode']!=0:raise ConfigError('nmap did not complete successfully.')
        stdout=result['stdout'].encode('utf-8')
        tree = ET.fromstring(stdout)
        observations = [{"port": p.get("portid"), "state": p.find("state").get("state") if p.find("state") is not None else "unknown", "service": dict(p.find("service").attrib) if p.find("service") is not None else {}} for p in tree.findall(".//port")]
        return {"host": host, "observations": observations, "xml_sha256": hashlib.sha256(stdout).hexdigest(), "note": "Service observations are not verified vulnerabilities."}
