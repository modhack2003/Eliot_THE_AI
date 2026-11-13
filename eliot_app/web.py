"""Loopback-only web application with same-origin mutation checks."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
import secrets

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .config import ConfigError, Provider, Settings
from .gateway import ProviderError
from .service import Service
from .store import BusyError
from .mission_runtime import MissionRuntime
from .instructions import CORE_SYSTEM
from .policy import MissionOptions
from .contracts import SuccessCheck
from .scheduler import Scheduler, ScheduleInput


class NewSession(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=120)


class Chat(BaseModel):
    content: str = Field(min_length=1, max_length=16_000)
    provider_id: str | None = None
    persona_id: str = "eliot"


class NewTask(BaseModel):
    objective: str = Field(min_length=1, max_length=12_000)
    workspace: str
    provider_id: str | None = None
    persona_id: str = "eliot"
    skills: list[str] | None = Field(default=None, max_length=12)
    targets: list[str] = Field(default_factory=list, max_length=100)
    network: bool = False
    max_steps: int = Field(default=0, ge=0)
    token_budget: int = Field(default=0, ge=0)
    max_workers: int = Field(default=3, ge=1, le=6)
    options: MissionOptions = Field(default_factory=MissionOptions)
    success_checks: list[SuccessCheck] = Field(default_factory=list,max_length=30)


class PersonaInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    instructions: str = Field(min_length=1, max_length=12_000)


class TaskFeedback(BaseModel):
    text: str = Field(min_length=1, max_length=6000)


class TaskResume(BaseModel):
    rebind_provider: bool = False
    max_steps: int | None = Field(default=None, ge=0)
    token_budget: int | None = Field(default=None, ge=0)


class Profile(BaseModel):
    id: str
    name: str
    base_url: str
    model: str
    api_key_env: str = "ELIOT_API_KEY"
    auth: str = "bearer"
    streaming: bool = True
    timeout_seconds: float = 60
    max_retries: int = 1
    parameters: dict = Field(default_factory=dict)
    context_chars: int = 80000
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    vision: bool = False
    structured_output: bool = False


class TemporaryKey(BaseModel):
    api_key: str = Field(min_length=1, max_length=4096)


def create_app(config_path=None, gateway=None, external_worker=False):
    settings = Settings(config_path)
    service = Service(settings, gateway)
    missions = MissionRuntime(service,execute_tasks=not external_worker)
    scheduler = Scheduler(missions)
    csrf_token = secrets.token_urlsafe(32)
    key_tests = set()

    @asynccontextmanager
    async def lifespan(app):
        service.store.recover()
        if not external_worker:
            scheduler.start()
            missions.recover()
        try:
            yield
        finally:
            await scheduler.close()
            await missions.close()
            await service.close()

    app = FastAPI(title="Eliot Remastered", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.service = service
    app.state.missions = missions
    app.state.scheduler = scheduler
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"])

    @app.middleware("http")
    async def local_access(request: Request, call_next):
        host = request.client.host if request.client else ""
        if host not in {"127.0.0.1", "::1", "testclient"}:
            return JSONResponse({"detail": "This release accepts local connections only."}, status_code=403)
        # An explicit Origin is checked for reads as well, including browser GETs.
        origin = request.headers.get("origin")
        if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
            return JSONResponse({"detail": "Cross-origin requests are not allowed."}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if not secrets.compare_digest(request.headers.get("x-eliot-token", ""), csrf_token):
                return JSONResponse({"detail": "Refresh the page or reconnect the terminal client.", "code": "invalid_request_token"}, status_code=403)
            try:
                if int(request.headers.get("content-length", "0")) > 100_000:
                    return JSONResponse({"detail": "Request is too large."}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "Invalid content length."}, status_code=400)
            payload = await request.body()
            if len(payload) > 100_000:
                return JSONResponse({"detail": "Request is too large."}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.exception_handler(ConfigError)
    async def config_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.exception_handler(BusyError)
    async def busy_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.exception_handler(KeyError)
    async def not_found(request, error):
        return JSONResponse({"detail": "The conversation or response was not found."}, status_code=404)

    @app.exception_handler(ProviderError)
    async def provider_error(request, error):
        return JSONResponse({"detail": str(error), "kind": error.kind}, status_code=502)

    # Validation responses must not echo submitted API keys or other input values.
    from fastapi.exceptions import RequestValidationError
    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse({"detail": "Invalid input. Check the required fields and input lengths."}, status_code=422)

    @app.get("/api/bootstrap")
    async def bootstrap():
        return {"version": __version__, "token": csrf_token, "default_provider": settings.default_provider, "providers": service.providers()}

    @app.get("/api/providers")
    async def providers():
        return service.providers()

    @app.put("/api/providers/{provider_id}")
    async def save_provider(provider_id: str, profile: Profile):
        if profile.id != provider_id:
            raise HTTPException(400, "Provider ID does not match the URL.")
        provider = Provider(**profile.model_dump())
        old = settings.providers.get(provider_id)
        if provider_id in key_tests or any(service.store.run(run_id)["provider_id"] == provider_id for run_id in service.tasks):
            raise BusyError("Stop this provider's active responses before changing its profile.")
        settings.save_provider(provider)
        # A temporary secret must never silently follow a changed endpoint.
        if old and old.base_url.rstrip("/") != provider.base_url.rstrip("/"):
            service.gateway.runtime_keys.pop(provider_id, None)
        return {"saved": True}

    @app.post("/api/providers/{provider_id}/default")
    async def select_provider(provider_id: str):
        settings.select_default(provider_id)
        return {"saved": True}

    @app.delete("/api/providers/{provider_id}")
    async def delete_provider(provider_id: str):
        if provider_id in key_tests or any(service.store.run(run_id)["provider_id"] == provider_id for run_id in service.tasks):
            raise BusyError("Stop this provider's active responses before deleting its profile.")
        settings.delete_provider(provider_id)
        service.gateway.runtime_keys.pop(provider_id, None)
        return {"deleted": True}

    @app.put("/api/providers/{provider_id}/key")
    async def set_temporary_key(provider_id: str, item: TemporaryKey):
        service.provider(provider_id)
        if not item.api_key.strip():
            raise ConfigError("Enter a nonempty API key.")
        service.gateway.runtime_keys[provider_id] = item.api_key.strip()
        return {"saved": True, "storage": "memory_until_backend_exit"}

    @app.delete("/api/providers/{provider_id}/key")
    async def forget_key(provider_id: str):
        service.provider(provider_id)
        service.gateway.runtime_keys.pop(provider_id, None)
        return {"deleted": True}

    @app.post("/api/providers/{provider_id}/test")
    async def test_provider(provider_id: str):
        provider = service.provider(provider_id)
        if provider_id in key_tests:
            raise BusyError("A connection test is already running for this provider.")
        key_tests.add(provider_id)
        try:
            async with asyncio.timeout(30):
                result = await service.gateway.complete(provider, [{"role": "user", "content": "Reply with OK only."}])
            return {"status": "healthy", "model": provider.model, "finish_reason": result.finish_reason}
        except TimeoutError:
            raise ProviderError("timeout", "The connection test timed out.") from None
        finally:
            key_tests.discard(provider_id)

    @app.get("/api/sessions")
    async def sessions():
        return service.store.list_sessions()

    @app.post("/api/sessions")
    async def new_session(item: NewSession):
        return service.store.create_session(item.title.strip() or "New conversation")

    @app.get("/api/sessions/{session_id}")
    async def session(session_id: str):
        return service.store.session(session_id)

    @app.delete("/api/sessions/{session_id}")
    async def delete_session(session_id: str):
        service.store.delete_session(session_id)
        return {"deleted": True}

    @app.get("/api/sessions/{session_id}/export")
    async def export(session_id: str):
        return JSONResponse(service.store.session(session_id), headers={"Content-Disposition": f'attachment; filename="eliot-session-{service.store.session(session_id)["id"]}.json"'})

    @app.post("/api/sessions/{session_id}/runs")
    async def chat(session_id: str, item: Chat):
        if not item.content.strip():
            raise ConfigError("Enter a message.")
        return service.start(session_id, item.content.strip(), item.provider_id, item.persona_id)

    @app.get("/api/instructions")
    async def instructions():
        import hashlib
        return {"system": CORE_SYSTEM, "sha256": hashlib.sha256(CORE_SYSTEM.encode()).hexdigest(), "hierarchy": ["system and runtime permissions", "persona", "skills", "task and external data"]}

    @app.get("/api/skills")
    async def skills():
        return missions.catalog.list()

    @app.get("/api/skills/{skill_id}")
    async def skill_page(skill_id: str, start_line: int = 1, resource: str = "SKILL.md"):
        return missions.catalog.read(skill_id, resource=resource, start_line=start_line, limit=120)

    @app.get("/api/personas")
    async def personas():
        return missions.store.personas()

    @app.put("/api/personas/{persona_id}")
    async def upload_persona(persona_id: str, item: PersonaInput):
        return missions.store.save_persona(persona_id, item.name, item.instructions)

    @app.get("/api/tasks")
    async def task_list(limit: int = 50, offset: int = 0):
        return missions.store.summaries(limit=limit,offset=offset)

    @app.post("/api/tasks")
    async def create_task(item: NewTask):
        return missions.create(**item.model_dump())

    @app.get("/api/tasks/{task_id}")
    async def task_detail(task_id: str):
        mission = missions.store.get(task_id)
        return {**mission, "children": [m for m in missions.store.list(mission["root_id"]) if m["parent_id"] == task_id], "totals": missions.store.totals(mission["root_id"]), "metrics":missions.store.metrics(mission["root_id"])}

    @app.get("/api/tasks/{task_id}/events")
    async def task_events(task_id: str, after: int = 0):
        missions.store.get(task_id)
        return missions.store.events(task_id, after=max(0, after))

    @app.post("/api/tasks/{task_id}/feedback")
    async def task_feedback(task_id: str, item: TaskFeedback):
        missions.store.get(task_id)
        return {"event_id": missions.store.feedback(task_id, item.text)}

    @app.get('/api/model-performance')
    async def model_performance():
        from .routing import performance
        return performance(missions.store)

    @app.get('/api/capabilities')
    async def capabilities():
        return missions.tools.registry()

    @app.get('/api/tasks/{task_id}/export')
    async def export_task(task_id: str):
        mission=missions.store.get(task_id)
        members=missions.store.list(mission['root_id'])
        records=[]
        for member in members:
            after=0;events=[]
            while True:
                page=missions.store.events(member['id'],after=after,limit=500)
                events.extend(page)
                if len(page)<500:break
                after=page[-1]['id']
            records.append({'mission':member,'events':events,'actions':missions.store.actions(member['id'])})
        return JSONResponse({'tasks':records,'metrics':missions.store.metrics(mission['root_id'])},headers={'Content-Disposition':f'attachment; filename="eliot-mission-{task_id}.json"'})

    @app.get('/api/tasks/{task_id}/artifacts')
    async def artifacts(task_id: str):
        mission=missions.store.get(task_id)
        records=[]
        for member in missions.store.list(mission['root_id']):
            for action in missions.store.actions(member['id']):
                if json.loads(action['request'])['tool']=='write_artifact' and action['result'].get('ok'):
                    records.append({'owner':member['id'],**action['result']['output']})
        return records

    @app.get('/api/tasks/{task_id}/artifact')
    async def artifact(task_id: str,path: str):
        mission=missions.store.get(task_id)
        supplied=Path(path)
        owners={m['id'] for m in missions.store.list(mission['root_id'])}
        if len(supplied.parts)<3 or supplied.parts[0]!='.eliot-artifacts' or supplied.parts[1] not in owners:
            raise ConfigError('Artifact does not belong to this mission.')
        target=missions.tools.artifact_path(mission,Path(*supplied.parts[2:]),supplied.parts[1])
        if not target.is_file():raise KeyError(path)
        return FileResponse(target,filename=target.name,media_type='application/octet-stream')

    @app.get('/api/tasks/{task_id}/memory')
    async def task_memory(task_id: str,query: str='',scope: str='project',offset: int=0):
        return missions.tools.knowledge.recall(missions.store.get(task_id),query,scope,offset=max(0,offset))

    @app.put('/api/tasks/{task_id}/memory/{memory_id}')
    async def correct_memory(task_id: str,memory_id: str,request: Request):
        mission=missions.store.get(task_id)
        payload=await request.json()
        text=payload.get('text')
        if not isinstance(text,str) or not 1<=len(text)<=6000:raise ConfigError('Supply corrected memory text of up to 6,000 characters.')
        with service.store.connection() as db:row=db.execute('SELECT * FROM agent_memory WHERE id=?',(memory_id,)).fetchone()
        if not row or row['scope_key']!=missions.tools.knowledge.key(mission,row['scope']):raise KeyError(memory_id)
        saved=missions.tools.knowledge.remember(mission,text,row['source'],row['scope'],row['confidence'])
        if saved['id']!=memory_id:missions.tools.knowledge.forget(mission,memory_id)
        return saved

    @app.delete('/api/tasks/{task_id}/memory/{memory_id}')
    async def delete_memory(task_id: str,memory_id: str):
        return missions.tools.knowledge.forget(missions.store.get(task_id),memory_id)

    @app.get('/api/schedules')
    async def schedules():return scheduler.list()

    @app.post('/api/schedules')
    async def create_schedule(item: ScheduleInput):return scheduler.create(item.model_dump())

    @app.delete('/api/schedules/{schedule_id}')
    async def delete_schedule(schedule_id: str):return scheduler.delete(schedule_id)

    @app.post('/api/schedules/{schedule_id}/enabled')
    async def enable_schedule(schedule_id: str,request: Request):
        payload=await request.json()
        if type(payload.get('enabled')) is not bool:raise ConfigError('enabled must be a boolean.')
        return scheduler.set_enabled(schedule_id,payload['enabled'])

    @app.post('/api/schedules/{schedule_id}/trigger')
    async def trigger_schedule(schedule_id: str,request: Request):
        payload=await request.json()
        event_id=payload.get('event_id')
        if not isinstance(event_id,str):raise ConfigError('Supply a stable event identifier.')
        return scheduler.trigger(schedule_id,event_id)

    @app.post("/api/tasks/{task_id}/{action}")
    async def task_control(task_id: str, action: str, item: TaskResume | None = None):
        return await missions.control(task_id, action, **(item.model_dump() if item else {}))

    @app.get("/api/runs/{run_id}")
    async def run(run_id: str):
        return service.store.run(run_id)

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel(run_id: str):
        return await service.cancel(run_id)

    @app.get("/api/runs/{run_id}/events")
    async def events(run_id: str, request: Request):
        service.store.run(run_id)
        async def stream():
            previous = None
            while not await request.is_disconnected():
                run = service.store.run(run_id)
                serialized = json.dumps(run)
                if serialized != previous:
                    yield f"data: {serialized}\n\n"
                    previous = serialized
                if run["status"] not in {"queued", "running"}:
                    break
                await asyncio.sleep(0.15)
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})

    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")
    @app.get("/")
    async def index():
        return FileResponse(static / "index.html")
    return app
