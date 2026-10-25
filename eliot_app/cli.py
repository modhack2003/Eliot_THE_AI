"""Terminal client for the same local backend used by the web interface."""
from __future__ import annotations

import argparse
from getpass import getpass
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from . import __version__
from .config import ConfigError, Settings, loopback


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="eliot", description="Eliot Remastered — shared terminal and web assistant")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", help="Configuration file (or ELIOT_CONFIG)")
    parser.add_argument("--server", default="http://127.0.0.1:8765", help="Running local Eliot backend")
    commands = parser.add_subparsers(dest="command")
    serve = commands.add_parser("serve", help="Start the local backend and web interface")
    serve.add_argument("--port", type=int, default=8765)
    doctor = commands.add_parser("doctor", help="Check dependencies, storage, web assets and skill integrity offline")
    doctor.add_argument("--json", action="store_true", help="Machine-readable readiness report")
    doctor.add_argument("--strict", action="store_true", help="Exit unsuccessfully if a required check fails")
    doctor.add_argument("--require-nmap", action="store_true", help="Treat missing nmap as an error")
    chat = commands.add_parser("chat", help="Chat using the running backend")
    chat.add_argument("--session", help="Resume a saved session")
    chat.add_argument("--provider", help="Provider profile ID")
    chat.add_argument("--persona", default="eliot", help="Persona profile ID")
    commands.add_parser("sessions", help="List saved sessions")
    export = commands.add_parser("export", help="Export a session as JSON to stdout")
    export.add_argument("session_id")
    commands.add_parser("skills", help="List the bundled cybersecurity skills")
    persona = commands.add_parser("personas", help="List or import a subordinate text persona")
    persona.add_argument("--import-file")
    persona.add_argument("--id")
    persona.add_argument("--name")
    tasks = commands.add_parser("tasks", help="Create and manage durable cybersecurity tasks")
    task_actions = tasks.add_subparsers(dest="action")
    create = task_actions.add_parser("create")
    create.add_argument("objective")
    create.add_argument("--workspace", required=True)
    create.add_argument("--provider")
    create.add_argument("--persona", default="eliot")
    create.add_argument("--skill", action="append")
    create.add_argument("--target", action="append", default=[])
    create.add_argument("--network", action="store_true")
    create.add_argument("--max-steps", type=int, default=0)
    create.add_argument("--token-budget", type=int, default=0)
    create.add_argument("--max-workers", type=int, default=3)
    for action in ["show", "watch", "pause", "resume", "cancel", "feedback"]:
        item = task_actions.add_parser(action)
        item.add_argument("id")
        if action == "feedback":
            item.add_argument("text")
        if action == "resume":
            item.add_argument("--max-steps", type=int)
            item.add_argument("--token-budget", type=int)
    task_actions.add_parser("list")
    providers = commands.add_parser("providers", help="Manage providers through the running backend")
    actions = providers.add_subparsers(dest="action")
    actions.add_parser("list")
    add = actions.add_parser("add")
    add.add_argument("id")
    add.add_argument("--name")
    add.add_argument("--base-url", required=True)
    add.add_argument("--model", required=True)
    add.add_argument("--key-env", default="ELIOT_API_KEY")
    add.add_argument("--no-auth", action="store_true")
    add.add_argument("--no-stream", action="store_true")
    for action in ["test", "default", "key", "forget-key", "delete"]:
        actions.add_parser(action).add_argument("id")
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    try:
        if args.command == "serve":
            import uvicorn
            from .web import create_app
            if not 1 <= args.port <= 65535:
                raise ConfigError("Choose a port between 1 and 65535.")
            print(f"Eliot web interface: http://127.0.0.1:{args.port}")
            uvicorn.run(create_app(args.config), host="127.0.0.1", port=args.port, access_log=False)
            return
        if args.command == "doctor":
            from .diagnostics import diagnose
            report = diagnose(args.config, require_nmap=args.require_nmap)
            if args.json:
                print(json.dumps(report, indent=2, ensure_ascii=False))
            else:
                print(f"Eliot {__version__} — installation checks")
                for check in report["checks"]:
                    print(f'{check["status"].upper():7} {check["name"]}: {check["detail"]}')
                print("No API calls or scans were made. Start with: eliot serve")
            if args.strict and not report["ready"]:
                raise SystemExit(1)
            return
        url = urlsplit(args.server)
        if url.scheme != "http" or not url.hostname or not loopback(url.hostname) or url.username or url.password or url.query or url.fragment:
            raise ConfigError("The terminal client connects to a local http:// backend only.")
        with httpx.Client(base_url=args.server.rstrip("/"), timeout=650, trust_env=False) as client:
            state = request(client, "GET", "/api/bootstrap")
            client.headers["X-Eliot-Token"] = state["token"]
            if args.command == "sessions":
                for session in request(client, "GET", "/api/sessions"):
                    print(f'{session["id"]}  {session["title"]}')
            elif args.command == "export":
                print(json.dumps(request(client, "GET", f"/api/sessions/{args.session_id}/export"), indent=2, ensure_ascii=False))
            elif args.command == "providers":
                provider_commands(client, args)
            elif args.command == "chat":
                chat_loop(client, args)
            elif args.command == "skills":
                for skill in request(client, "GET", "/api/skills"):
                    print(skill["id"] + ": " + skill["description"][:180])
            elif args.command == "personas":
                if args.import_file:
                    if not args.id or not args.name:
                        raise ValueError("Persona import requires --id and --name.")
                    path = Path(args.import_file)
                    if path.stat().st_size > 48_000:
                        raise ValueError("Persona file is too large.")
                    text = path.read_text(encoding="utf-8")
                    request(client, "PUT", f"/api/personas/{args.id}", json={"name": args.name, "instructions": text})
                    print("Persona imported below the fixed system rules.")
                else:
                    for item in request(client, "GET", "/api/personas"):
                        print(item["id"] + ": " + item["name"])
            elif args.command == "tasks":
                task_commands(client, args)
    except (ConfigError, ValueError, httpx.HTTPError, OSError) as error:
        if isinstance(error, httpx.HTTPError):
            print("Cannot connect to Eliot. Start the backend with: eliot serve", file=sys.stderr)
        else:
            print(str(error), file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nEliot closed.")


def request(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    if response.is_error:
        raise ValueError(response.json().get("detail", "The request failed."))
    return response.json()


def provider_commands(client, args):
    action = args.action or "list"
    if action == "list":
        for profile in request(client, "GET", "/api/providers"):
            print(f'{"*" if profile["is_default"] else " "} {profile["id"]}: {profile["model"]} — {profile["base_url"]} ({"ready" if profile["key_configured"] else "key needed"})')
    elif action == "add":
        item = dict(id=args.id, name=args.name or args.id, base_url=args.base_url, model=args.model, api_key_env=args.key_env, auth="none" if args.no_auth else "bearer", streaming=not args.no_stream)
        request(client, "PUT", f"/api/providers/{args.id}", json=item)
        print("Provider saved. Set its key environment variable before backend startup, or use: eliot providers key " + args.id)
    elif action == "key":
        value = getpass("API key (kept in backend memory until it exits): ")
        request(client, "PUT", f"/api/providers/{args.id}/key", json={"api_key": value})
        print("Temporary key set.")
    elif action == "forget-key":
        request(client, "DELETE", f"/api/providers/{args.id}/key")
        print("Temporary key forgotten. Environment-backed keys remain configured.")
    elif action == "delete":
        request(client, "DELETE", f"/api/providers/{args.id}")
        print("Provider deleted.")
    else:
        result = request(client, "POST", f"/api/providers/{args.id}/{action}")
        print("Connection test passed." if action == "test" else "Default provider saved.")


def task_commands(client, args):
    action = args.action or "list"
    if action == "create":
        payload = dict(objective=args.objective, workspace=str(Path(args.workspace).resolve()), provider_id=args.provider, persona_id=args.persona, skills=args.skill, targets=args.target, network=args.network, max_steps=args.max_steps, token_budget=args.token_budget, max_workers=args.max_workers)
        result = request(client, "POST", "/api/tasks", json=payload)
        print("Task started: " + result["id"])
        print("The backend owns this task; disconnecting the terminal does not stop it.")
    elif action == "list":
        for item in request(client, "GET", "/api/tasks"):
            print(f'{item["id"]}  {item["status"]}  {item["objective"][:90]}')
    elif action == "show":
        print(json.dumps(request(client, "GET", f"/api/tasks/{args.id}"), indent=2, ensure_ascii=False))
    elif action == "feedback":
        request(client, "POST", f"/api/tasks/{args.id}/feedback", json={"text": args.text})
        print("Feedback recorded for the next planning turn. Resume explicitly if the task is blocked or paused.")
    elif action == "watch":
        after = 0
        try:
            while True:
                events = request(client, "GET", f"/api/tasks/{args.id}/events?after={after}")
                for event in events:
                    print(f'{event["id"]} {event["kind"]}: {json.dumps(event["data"], ensure_ascii=False)}')
                    after = event["id"]
                if len(events) == 100:
                    continue
                item = request(client, "GET", f"/api/tasks/{args.id}")
                if item["status"] in {"completed", "blocked", "cancelled", "paused", "budget_exhausted"}:
                    print(item["status"] + ": " + (item["result"] or item["reason"]))
                    return
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopped watching; task continues in the backend.")
    else:
        payload = {"max_steps": args.max_steps, "token_budget": args.token_budget} if action == "resume" else None
        result = request(client, "POST", f"/api/tasks/{args.id}/{action}", json=payload)
        print(result["status"])


def chat_loop(client, args):
    session = request(client, "GET", f"/api/sessions/{args.session}") if args.session else request(client, "POST", "/api/sessions", json={})
    session_id, provider_id = session["id"], args.provider
    for message in session.get("messages", []):
        print(f'{message["role"]}: {message["content"]}\n')
    print(f"Session: {session_id}\n/new starts a conversation; /provider ID switches model; /exit closes chat. Ctrl+C stops an active response.")
    while True:
        try:
            text = input("\nYou > ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if text == "/exit":
            return
        if text == "/new":
            session_id = request(client, "POST", "/api/sessions", json={})["id"]
            print("Session: " + session_id)
            continue
        if text.startswith("/provider "):
            provider_id = text.split(maxsplit=1)[1]
            print("Provider: " + provider_id)
            continue
        if not text:
            continue
        run = None
        try:
            run = request(client, "POST", f"/api/sessions/{session_id}/runs", json={"content": text, "provider_id": provider_id, "persona_id": args.persona})
            print("\nEliot > ", end="", flush=True)
            length = 0
            with client.stream("GET", f'/api/runs/{run["id"]}/events') as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line.startswith("data:"):
                        current = json.loads(line[5:])
                        print(current["text"][length:], end="", flush=True)
                        length = len(current["text"])
                        if current["error"]:
                            print("\n" + current["error"])
                        elif current["status"] == "completed" and current["finish_reason"] == "length":
                            print("\n[Model output limit reached]")
            print()
        except KeyboardInterrupt:
            if run:
                request(client, "POST", f'/api/runs/{run["id"]}/cancel')
            print("\nResponse stopped.")
        except ValueError as error:
            print(error)


if __name__ == "__main__":
    main()
