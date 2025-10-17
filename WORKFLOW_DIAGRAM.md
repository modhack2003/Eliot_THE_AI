# ELIOT Detailed Workflow Diagram

## 🎯 COMPLETE SYSTEM WORKFLOW

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                ELIOT STARTUP                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          main.py → ELIOTAssistant.__init__()                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 1. _configure_python_path()                                                    │
│    ├── Add user site-packages to sys.path                                      │
│    ├── Handle sudo scenarios                                                   │
│    └── Configure for Google Generative AI                                     │
│                                                                                 │
│ 2. ConfigManager()                                                             │
│    ├── Load config.yaml                                                       │
│    ├── Validate configuration                                                  │
│    └── Get MongoDB connection string                                          │
│                                                                                 │
│ 3. LLMManager()                                                               │
│    ├── Load API keys from config                                               │
│    ├── Initialize Gemini providers                                             │
│    └── Setup API key status tracking                                          │
│                                                                                 │
│ 4. _init_mongodb()                                                            │
│    ├── Connect to MongoDB Atlas                                                │
│    ├── Test connection                                                         │
│    └── Setup token usage tracking                                             │
│                                                                                 │
│ 5. MCPClient()                                                                │
│    ├── Connect to kali-server-mcp                                             │
│    ├── Test health endpoint                                                    │
│    └── Setup command execution                                                │
│                                                                                 │
│ 6. Initialize session context                                                  │
│    ├── targets: []                                                            │
│    ├── scan_results: {}                                                       │
│    ├── vulnerabilities: []                                                    │
│    ├── exploits_tried: []                                                     │
│    └── credentials_found: []                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        run() → Startup API Testing                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│ _test_api_keys_startup()                                                       │
│ ├── For each provider (Gemini):                                               │
│ │   ├── For each API key:                                                     │
│ │   │   ├── print("Testing Key X...")                                        │
│ │   │   ├── _test_api_key_real(key)                                          │
│ │   │   │   ├── Configure genai with key                                     │
│ │   │   │   ├── model.generate_content("Test")                               │
│ │   │   │   ├── Check response.text                                          │
│ │   │   │   ├── _track_token_usage() → MongoDB                               │
│ │   │   │   └── Return {"working": True/False, "status": "✅/❌"}            │
│ │   │   ├── print("Key X: ✅ Available / ❌ Quota exceeded")                 │
│ │   │   ├── Update usage_count if working                                    │
│ │   │   └── Mark rate_limited_until if quota exceeded                        │
│ │   └── Display key status                                                   │
│ └── Show summary: "X/Y API keys working"                                     │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Main Interactive Loop                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│ while True:                                                                     │
│   ├── user_input = await asyncio.to_thread(input, "🔹 ELIOT > ")              │
│   ├── if user_input.lower() in ['quit', 'exit']: break                        │
│   ├── response = await process_message(user_input)                             │
│   └── print(response)                                                          │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        process_message() → Command Router                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│ user_input = user_input.strip()                                                │
│                                                                                 │
│ 1. Direct Commands (No AI needed):                                             │
│    ├── if user_input.lower() in ['help', 'status', 'clear', 'quota']:        │
│    │   ├── help → show_help()                                                  │
│    │   ├── status → handle_status_request()                                    │
│    │   ├── clear → clear session_context                                       │
│    │   ├── quota → _check_api_status()                                         │
│    │   ├── tools → _list_available_tools()                                     │
│    │   └── add key → _add_user_api_key()                                       │
│                                                                                 │
│ 2. Shell Command Detection:                                                    │
│    ├── shell_commands = ['ls', 'pwd', 'ping', 'ifconfig', ...]               │
│    ├── first_word = user_input.split()[0].lower()                             │
│    ├── is_question = ('?' in user_input or question_words)                    │
│    ├── if (first_word in shell_commands or starts_with_path) and not is_question:
│    │   └── return _execute_shell_command(user_input)                          │
│                                                                                 │
│ 3. AI-Driven Processing:                                                       │
│    ├── Build context from session                                              │
│    ├── Create AI prompt with available tools                                   │
│    ├── Show loading animation                                                  │
│    ├── llm_response = llm_manager.generate_text(prompt)                       │
│    ├── if response.startswith("TOOL_EXECUTE:"):                               │
│    │   └── return _execute_ai_command(command, user_input)                    │
│    └── else: return f"🤖 {response}"                                          │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      _execute_shell_command() → Direct Execution               │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 1. Handle 'cd' specially:                                                      │
│    ├── if command.startswith('cd '):                                          │
│    │   ├── path = command[3:].strip()                                         │
│    │   ├── os.chdir(path)                                                     │
│    │   └── return f"📁 Changed directory to: {os.getcwd()}"                   │
│                                                                                 │
│ 2. Execute other commands:                                                     │
│    ├── print(f"⚡ Executing: {command}")                                       │
│    ├── result = subprocess.run(command, shell=True, capture_output=True,      │
│    │                           text=True, timeout=60, cwd=os.getcwd())        │
│    │                                                                           │
│    ├── Format output with boxes:                                               │
│    │   ├── if return_code == 0:                                               │
│    │   │   └── ╔══════════════════════════════════════════════════════════════╗
│    │   │       ║ ✅ Command Executed Successfully                             ║
│    │   │       ╠══════════════════════════════════════════════════════════════╣
│    │   │       ║ {output}                                                     ║
│    │   │       ╚══════════════════════════════════════════════════════════════╝
│    │   └── else:                                                              │
│    │       └── ╔══════════════════════════════════════════════════════════════╗
│    │           ║ ❌ Command Failed                                            ║
│    │           ║ Exit Code: {return_code}                                     ║
│    │           ╠══════════════════════════════════════════════════════════════╣
│    │           ║ {output + error}                                             ║
│    │           ╚══════════════════════════════════════════════════════════════╝
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     _execute_ai_command() → MCP Execution                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 1. Extract target from original_input:                                         │
│    ├── target = extract_scan_target(original_input)                           │
│    ├── if target and target not in session_context['targets']:                │
│    │   └── session_context['targets'].append(target)                          │
│                                                                                 │
│ 2. Display appropriate message:                                                │
│    ├── if command.startswith('ping'): "🏓 Running connectivity test..."       │
│    ├── elif command.startswith('nmap'):                                       │
│    │   ├── if '--script=vuln': "🎯 Running comprehensive vulnerability scan..." │
│    │   └── else: "🔍 Running network reconnaissance..."                       │
│    ├── elif command.startswith('nikto'): "🌐 Running web application security scan..." │
│    └── else: "🔧 Running pentesting tool..."                                  │
│                                                                                 │
│ 3. Execute via MCP:                                                            │
│    ├── timeout = 900 if '--script=vuln' in command else 300                   │
│    ├── result = mcp_client.execute_command(command, timeout=timeout)          │
│    │   ├── POST /api/command to kali-server-mcp                               │
│    │   ├── Send: {"command": command}                                          │
│    │   ├── Wait for response with timeout                                     │
│    │   └── Return: {"stdout": output, "stderr": error, "return_code": code}   │
│                                                                                 │
│ 4. Format results:                                                             │
│    ├── if result.get('stdout') or result.get('stderr'):                       │
│    │   ├── ╔══════════════════════════════════════════════════════════════╗
│    │   ├── ║ 🎯 Pentesting Tool Results                                   ║
│    │   ├── ╠══════════════════════════════════════════════════════════════╣
│    │   ├── ║ Command: {command}                                           ║
│    │   ├── ║ Status: ✅ Success / ❌ Failed (Exit Code: {return_code})    ║
│    │   ├── ╠══════════════════════════════════════════════════════════════╣
│    │   ├── ║ {output}                                                     ║
│    │   ├── ║ {error if present}                                           ║
│    │   └── ╚══════════════════════════════════════════════════════════════╝
│    │                                                                           │
│    ├── Store in session_context:                                              │
│    │   └── session_context['scan_results'][target] = {command, result, ...}   │
│    └── return formatted_result                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           API Key Management                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│ _add_user_api_key():                                                           │
│ ├── Prompt: "🔑 Enter your Gemini API key: "                                  │
│ ├── api_key = await asyncio.to_thread(input)                                  │
│ ├── _test_api_key(api_key):                                                   │
│ │   ├── genai.configure(api_key=api_key)                                      │
│ │   ├── model = genai.GenerativeModel('gemini-2.5-pro')                      │
│ │   ├── response = model.generate_content("Test")                             │
│ │   └── return response.text is not None                                      │
│ ├── if test successful:                                                       │
│ │   ├── _save_api_key_to_config(api_key):                                    │
│ │   │   ├── Read config.yaml                                                  │
│ │   │   ├── Add key to providers[gemini][api_keys]                           │
│ │   │   └── Write back to config.yaml                                         │
│ │   ├── Reload LLMManager with new key                                        │
│ │   └── print("✅ API key added successfully!")                              │
│ └── else: print("❌ Invalid API key")                                         │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          MongoDB Token Tracking                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│ _track_token_usage(api_key, operation, tokens_used):                          │
│ ├── if not self.db: return                                                    │
│ ├── collection = self.db['api_usage']                                         │
│ ├── usage_record = {                                                          │
│ │   ├── 'api_key': api_key[:10] + "...",  # Privacy protection               │
│ │   ├── 'operation': operation,                                               │
│ │   ├── 'tokens_used': tokens_used,                                           │
│ │   ├── 'timestamp': datetime.utcnow(),                                       │
│ │   └── 'session_id': id(self)                                                │
│ │   }                                                                          │
│ ├── collection.insert_one(usage_record)                                       │
│ └── Handle exceptions gracefully                                              │
│                                                                                 │
│ _check_api_status_detailed():                                                  │
│ ├── Show API key status                                                        │
│ ├── if self.db:                                                               │
│ │   ├── total_usage = collection.count_documents({})                          │
│ │   ├── today_usage = collection.count_documents({                            │
│ │   │   'timestamp': {'$gte': start_of_day}                                   │
│ │   │   })                                                                    │
│ │   └── print(f"📊 Token Usage Tracking: {today_usage} today, {total_usage} total") │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              MCP Client                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│ MCPClient.execute_command(command, timeout=300):                               │
│ ├── url = "http://localhost:5000/api/command"                                  │
│ ├── payload = {"command": command}                                             │
│ ├── response = requests.post(url, json=payload, timeout=timeout)              │
│ ├── if response.status_code == 200:                                            │
│ │   ├── result = response.json()                                               │
│ │   ├── return {                                                               │
│ │   │   ├── "stdout": result.get("stdout", ""),                               │
│ │   │   ├── "stderr": result.get("stderr", ""),                               │
│ │   │   ├── "return_code": result.get("return_code", 0),                      │
│ │   │   └── "success": result.get("success", False)                           │
│ │   │   }                                                                      │
│ │   └── else: return {"error": f"HTTP {response.status_code}"}                │
│ └── except Exception as e: return {"error": str(e)}                           │
│                                                                                 │
│ MCPClient.check_health():                                                      │
│ ├── url = "http://localhost:5000/health"                                       │
│ ├── response = requests.get(url, timeout=5)                                    │
│ └── return response.status_code == 200                                         │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 🔄 DATA FLOW SUMMARY

```
User Input → Command Router → [Shell Commands | AI Processing]
    │                              │                    │
    │                              ▼                    ▼
    │                    subprocess.run()        LLM Manager
    │                              │                    │
    │                              ▼                    ▼
    │                      Direct Output         MCP Client
    │                              │                    │
    │                              ▼                    ▼
    │                      Formatted Result    kali-server-mcp
    │                              │                    │
    │                              ▼                    ▼
    │                      Display to User     Tool Execution
    │                              │                    │
    │                              ▼                    ▼
    │                      Session Update      Results to User
```

## 🎯 KEY COMPONENTS INTERACTION

1. **Main Application** (main.py) - Central coordinator
2. **Config Manager** - Configuration and MongoDB connection
3. **LLM Manager** - API key management and AI requests
4. **MCP Client** - Communication with Kali tools server
5. **MongoDB** - Token usage tracking and analytics
6. **Session Context** - Maintains state across interactions
7. **Command Router** - Decides shell vs AI processing
8. **Output Formatter** - Professional UI with boxes and styling

## 🚀 PRODUCTION READINESS

✅ **Error Handling**: Comprehensive exception handling
✅ **Health Checks**: MCP server and API key validation
✅ **Graceful Degradation**: Works without AI or MongoDB
✅ **Security**: API keys in config, partial key storage
✅ **Performance**: Async operations, connection pooling
✅ **Monitoring**: Token usage tracking, session persistence
✅ **Documentation**: Complete setup and deployment guides
✅ **Deployment**: Automated scripts for Kali Linux
