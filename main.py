#!/usr/bin/env python3
"""
ELIOT - AI Pentesting Assistant (MCP Version)
Simplified version using Kali MCP server
"""

import sys
import os
import time
import contextlib
import io
import yaml
import pymongo
from pymongo import MongoClient
from datetime import datetime

# Suppress Gemini warnings from the very beginning
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['ABSL_LOG_LEVEL'] = '3'
os.environ['GLOG_minloglevel'] = '3'

# Suppress Python warnings
import warnings
warnings.filterwarnings("ignore")

# Redirect stderr to suppress warnings (will be restored later)
original_stderr = sys.stderr
devnull = io.open(os.devnull, 'w')
sys.stderr = devnull

# CRITICAL: Add Python paths BEFORE any other imports
# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Add user local packages to Python path - multiple attempts
# Check both current user and original user (for sudo scenarios)
current_user = os.getenv('SUDO_USER') or os.getenv('USER') or 'kali'
possible_paths = [
    # Current user paths
    os.path.expanduser("~/.local/lib/python3.13/site-packages"),
    os.path.expanduser("~/.local/lib/python3.12/site-packages"),
    os.path.expanduser("~/.local/lib/python3.11/site-packages"),
    os.path.expanduser("~/.local/lib/python3.10/site-packages"),
    # Original user paths (for sudo)
    f"/home/{current_user}/.local/lib/python3.13/site-packages",
    f"/home/{current_user}/.local/lib/python3.12/site-packages",
    f"/home/{current_user}/.local/lib/python3.11/site-packages",
    f"/home/{current_user}/.local/lib/python3.10/site-packages",
    # System-wide paths
    "/usr/local/lib/python3.13/dist-packages",
    "/usr/local/lib/python3.12/dist-packages",
    "/usr/local/lib/python3.11/dist-packages",
    "/usr/local/lib/python3.10/dist-packages"
]

for path in possible_paths:
    if os.path.exists(path):
        sys.path.insert(0, path)

# Now import other modules
import asyncio
import re
import json
import traceback
from typing import List, Optional, Dict, Any

# Force import google.generativeai if available
try:
    import google.generativeai as genai
except ImportError:
    # Try to find and add the package manually
    import glob
    
    # Check multiple locations for Google packages
    search_paths = [
        os.path.expanduser("~/.local/lib/python*/site-packages/google"),
        f"/home/{current_user}/.local/lib/python*/site-packages/google",
        "/usr/local/lib/python*/dist-packages/google",
        "/usr/lib/python*/dist-packages/google"
    ]
    
    for search_pattern in search_paths:
        google_paths = glob.glob(search_pattern)
        for path in google_paths:
            parent_dir = os.path.dirname(path)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
                try:
                    import google.generativeai as genai
                    break
                except ImportError:
                    continue
        else:
            continue
        break

from agent.config_manager import ConfigManager
from agent.llm_manager import LLMManager
from mcp_client import MCPClient


class ELIOTAssistant:
    """Simplified ELIOT using MCP server"""
    
    def __init__(self):
        # Initialize configuration and LLM
        self.config_manager = ConfigManager()
        self.llm_manager = LLMManager(self.config_manager)
        
        # Initialize MongoDB connection
        self.mongo_client = None
        self.db = None
        self._init_mongodb()
        
        # Initialize MCP client
        self.mcp_client = MCPClient()
        
        # Session context
        self.session_context = {
            'targets': [],
            'scan_results': {},
            'vulnerabilities': [],
            'exploits_tried': [],
            'credentials_found': []
        }
        
        # Check MCP server health
        if not self.mcp_client.check_health():
            print("⚠️  WARNING: MCP server not available. Please start it with: kali-server-mcp --port 5000")
    
    def _init_mongodb(self):
        """Initialize MongoDB connection for token tracking"""
        try:
            # Get MongoDB connection string from config
            connection_string = self.config_manager.get_connection_string()
            if connection_string:
                self.mongo_client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
                self.db = self.mongo_client.get_default_database()
                # Test connection
                self.mongo_client.admin.command('ping')
                print("📊 MongoDB connected for token tracking")
            else:
                print("⚠️  MongoDB not configured - token usage won't be tracked")
        except Exception as e:
            print(f"⚠️  MongoDB connection failed: {e}")
            self.mongo_client = None
            self.db = None
    
    async def _test_api_keys_startup(self) -> str:
        """Test API keys with real requests at startup"""
        if not self.llm_manager.providers:
            return "❌ No LLM providers configured"
        
        status_info = "🔍 API Status (Real Test):\n"
        current_time = time.time()
        working_keys = 0
        total_keys = 0
        
        for provider_name, provider in self.llm_manager.providers.items():
            status_info += f"\n📡 {provider_name.upper()}:\n"
            
            if provider_name == 'gemini':
                api_keys = provider.get('api_keys', [])
                total_keys = len(api_keys)
                
                for i, key in enumerate(api_keys, 1):
                    key_status = self.llm_manager.api_key_status.get(key)
                    
                    # Make a real test request
                    print(f"  Testing Key {i}...", end="", flush=True)
                    test_result = await self._test_api_key_real(key)
                    print(f"\r  Key {i}: {test_result['status']} {test_result['details']}")
                    
                    if test_result['working']:
                        working_keys += 1
                        if key_status:
                            key_status.usage_count += 1
                    else:
                        # Mark as rate limited if quota exceeded
                        if 'quota' in test_result['details'].lower():
                            if key_status:
                                key_status.rate_limited_until = current_time + 86400  # 24 hours
                        status_info += f"  Key {i}: {test_result['status']} {test_result['details']}\n"
        
        # Summary
        if working_keys > 0:
            status_info += f"\n✅ AI Status: {working_keys}/{total_keys} API keys working"
        else:
            status_info += f"\n❌ No working API keys available"
            
        status_info += "\n💡 Tip: Use 'quota' command anytime to check API status"
        return status_info
    
    async def _test_api_key_real(self, api_key: str) -> dict:
        """Test API key with a real request"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.5-pro')
            
            # Make a simple test request
            response = model.generate_content("Test")
            
            if response.text:
                # Track token usage in MongoDB
                await self._track_token_usage(api_key, "test", len(response.text.split()))
                return {"working": True, "status": "✅", "details": "Available"}
            else:
                return {"working": False, "status": "❌", "details": "No response"}
            
        except Exception as e:
            error_msg = str(e).lower()
            if "quota" in error_msg or "429" in error_msg:
                return {"working": False, "status": "❌", "details": "Quota exceeded"}
            else:
                return {"working": False, "status": "❌", "details": f"Error: {str(e)[:50]}"}
    
    async def _track_token_usage(self, api_key: str, operation: str, tokens_used: int):
        """Track token usage in MongoDB"""
        if not self.db:
            return
            
        try:
            collection = self.db['api_usage']
            usage_record = {
                'api_key': api_key[:10] + "...",  # Only store partial key for privacy
                'operation': operation,
                'tokens_used': tokens_used,
                'timestamp': datetime.utcnow(),
                'session_id': id(self)
            }
            collection.insert_one(usage_record)
        except Exception as e:
            print(f"⚠️  Could not track token usage: {e}")
    
    def extract_scan_target(self, text: str) -> Optional[str]:
        """Intelligently extract scan target from natural language"""
        text_lower = text.lower()
        
        # Check for network ranges (CIDR notation) first - prioritize this over single IPs
        cidr_match = re.search(r'\b\d+\.\d+\.\d+\.\d+/\d+\b', text)
        if cidr_match:
            return cidr_match.group()
        
        # Check for specific IP addresses
        ip_match = re.search(r'\b\d+\.\d+\.\d+\.\d+\b', text)
        if ip_match:
            return ip_match.group()
        
        # Check for URLs
        url_match = re.search(r'https?://[^\s]+', text)
        if url_match:
            return url_match.group()
        
        # Check for domain names
        domain_match = re.search(r'\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', text)
        if domain_match:
            return domain_match.group()
        
        # Handle "local network" requests
        if any(phrase in text_lower for phrase in ['local network', 'local area network', 'lan', 'local subnet']):
            # Try to detect local network automatically
            try:
                import subprocess
                result = subprocess.run(['ip', 'route', 'show', 'default'], capture_output=True, text=True)
                if result.returncode == 0:
                    # Extract network from default route
                    for line in result.stdout.split('\n'):
                        if 'default via' in line:
                            parts = line.split()
                            for i, part in enumerate(parts):
                                if part == 'via' and i + 1 < len(parts):
                                    gateway = parts[i + 1]
                                    # Get network from gateway IP
                                    gateway_parts = gateway.split('.')
                                    if len(gateway_parts) == 4:
                                        network = f"{gateway_parts[0]}.{gateway_parts[1]}.{gateway_parts[2]}.0/24"
                                        return network
            except:
                pass
            # Fallback to common local networks
            return "192.168.1.0/24"
        
        return None
    
    async def handle_scan_request(self, target: str) -> str:
        """Handle network scanning requests using MCP"""
        print(f"🔍 Scanning {target}...")
        
        try:
            # Add to session context
            if target not in self.session_context['targets']:
                self.session_context['targets'].append(target)
            
            # Determine scan type and run appropriate commands
            if self.is_web_command(target):
                # Web application scan
                command = f"nikto -h {target}"
                print(f"🌐 Running web scan: {command}")
            else:
                # Network scan
                if '/' in target:
                    # Network range - host discovery
                    command = f"nmap -sn -T4 {target}"
                    print(f"📡 Running network discovery: {command}")
                else:
                    # Single host - port scan
                    command = f"nmap -sS -sV -O -A --script=vuln -T4 -Pn {target}"
                    print(f"🎯 Running port scan: {command}")
            
            # Execute via MCP - use longer timeout for comprehensive scans
            timeout = 900 if '--script=vuln' in command else 300  # 15 min for vuln scans, 5 min for others
            if timeout > 300:
                print("⏳ Comprehensive scan in progress (this may take up to 15 minutes)...")
            result = self.mcp_client.execute_command(command, timeout=timeout)
            
            if result.get('success', False):
                output = result.get('stdout', '')
                error = result.get('stderr', '')
                
                scan_result = f"📡 Scan Results for {target}:\n"
                scan_result += "=" * 50 + "\n"
                scan_result += output
                
                if error:
                    scan_result += "\n" + "=" * 50 + "\n"
                    scan_result += "Additional Info:\n"
                    scan_result += error
                
                # Store results
                self.session_context['scan_results'][target] = {
                    'type': 'web' if self.is_web_command(target) else 'network',
                    'result': scan_result,
                    'raw_output': output
                }
                
                return scan_result
            else:
                error_msg = result.get('error', 'Unknown error')
                return f"❌ Scan failed for {target}: {error_msg}"
            
        except Exception as e:
            return f"❌ Network scan failed for {target}: {e}"
    
    def is_web_command(self, target: str) -> bool:
        """Check if target is a web application"""
        return target.startswith(('http://', 'https://')) or '.com' in target or '.org' in target
    
    async def process_message(self, user_input: str) -> str:
        """Process user input with AI-driven tool usage"""
        user_input = user_input.strip()
        
        if not user_input:
            return "Please enter a command or ask a question."
        
        # Show loading indicator for AI processing
        print("🤔 Processing", end="", flush=True)
        
        # Handle direct commands (no loading needed)
        if user_input.lower() in ['help', 'status', 'clear', 'quota', 'api status']:
            print("\r" + " " * 20 + "\r", end="", flush=True)  # Clear loading indicator
            
            if user_input.lower() == 'help':
                return self.show_help()
            elif user_input.lower() == 'status':
                return await self.handle_status_request()
            elif user_input.lower() == 'clear':
                self.session_context = {
                    'targets': [],
                    'scan_results': {},
                    'vulnerabilities': [],
                    'exploits_tried': [],
                    'credentials_found': []
                }
                return "🧹 Session cleared!"
            elif user_input.lower() in ['quota', 'api status']:
                return self._check_api_status()
            elif user_input.lower() in ['tools', 'list tools', 'kali tools']:
                return self._list_available_tools()
            elif user_input.lower() in ['add key', 'add api key', 'addkey']:
                await self._add_user_api_key()
                return "✅ Use 'quota' command to check API key status"
        
        # Check if it's a simple shell command first
        shell_commands = [
            # File operations
            'ls', 'pwd', 'cd', 'cat', 'head', 'tail', 'grep', 'find', 'locate', 'which', 'whereis',
            'mkdir', 'rmdir', 'rm', 'cp', 'mv', 'ln', 'touch', 'chmod', 'chown', 'chgrp',
            'tar', 'zip', 'unzip', 'gzip', 'gunzip', 'bzip2', 'bunzip2',
            
            # System info
            'whoami', 'id', 'who', 'w', 'ps', 'top', 'htop', 'df', 'du', 'free', 'uname', 'date', 'uptime', 'hostname',
            'lscpu', 'lsmem', 'lsblk', 'lspci', 'lsusb', 'lsof', 'fuser',
            
            # Network tools
            'ifconfig', 'ip', 'netstat', 'ss', 'ping', 'traceroute', 'nslookup', 'dig', 'host',
            'wget', 'curl', 'nc', 'telnet', 'ssh', 'scp', 'rsync', 'ftp', 'sftp',
            'iwconfig', 'iwlist', 'iw', 'airmon-ng', 'airodump-ng', 'aireplay-ng', 'aircrack-ng',
            
            # System management
            'systemctl', 'service', 'journalctl', 'dmesg', 'lsmod', 'modinfo', 'insmod', 'rmmod',
            'iptables', 'ufw', 'firewall-cmd', 'crontab', 'at',
            
            # Text processing
            'awk', 'sed', 'cut', 'sort', 'uniq', 'wc', 'tr', 'diff', 'patch',
            
            # Process management
            'kill', 'killall', 'pkill', 'pgrep', 'nohup', 'screen', 'tmux',
            
            # Shell builtins and utilities
            'history', 'man', 'info', 'help', 'apropos', 'whatis', 'compgen', 'compopt',
            'alias', 'unalias', 'export', 'env', 'printenv', 'set', 'unset',
            'echo', 'printf', 'read', 'source', 'exec', 'eval', 'test', 'true', 'false',
            
            # Additional utilities
            'basename', 'dirname', 'realpath', 'stat', 'file', 'strings', 'od', 'hexdump',
            'seq', 'yes', 'sleep', 'timeout', 'watch', 'stty', 'tty', 'clear'
        ]
        
        # Check if input is a direct shell command (not a question)
        first_word = user_input.split()[0].lower() if user_input.split() else ""
        
        # Check if it's a question (contains question words or ends with ?)
        is_question = (
            user_input.endswith('?') or
            any(word in user_input.lower() for word in ['what', 'which', 'how', 'where', 'when', 'why', 'who']) or
            'tools you have' in user_input.lower() or
            'available' in user_input.lower()
        )
        
        # Only execute as shell command if it's clearly a command and not a question
        if (first_word in shell_commands or user_input.startswith('./') or user_input.startswith('/') or 
            user_input.startswith('sudo ') or user_input.startswith('su ')) and not is_question:
            print("\r" + " " * 20 + "\r", end="", flush=True)  # Clear loading indicator
            return await self._execute_shell_command(user_input)
        
        # AI-driven processing for pentesting tasks
        try:
            # Build context from session
            context = ""
            if self.session_context['targets']:
                context += f"Previous targets scanned: {', '.join(self.session_context['targets'])}\n"
            if self.session_context['vulnerabilities']:
                context += f"Vulnerabilities found: {len(self.session_context['vulnerabilities'])}\n"
            if self.session_context['scan_results']:
                context += f"Scan results available for: {', '.join(self.session_context['scan_results'].keys())}\n"
            
            # AI-driven tool selection for pentesting tasks only
            ai_prompt = f"""You are ELIOT, an AI pentesting assistant with DIRECT ACCESS to real pentesting tools on Kali Linux via MCP server.

AVAILABLE PENTESTING TOOLS (via MCP):
- nmap: Network scanning, port scanning, service detection, host discovery
- nikto: Web vulnerability scanner  
- sqlmap: SQL injection testing
- hydra: Password brute force
- gobuster/dirb: Directory enumeration
- ping: Network connectivity testing
- All other Kali Linux pentesting tools

CURRENT SESSION:
{context}

USER REQUEST: "{user_input}"

INSTRUCTIONS:
1. This is for PENTESTING TASKS and QUESTIONS - not basic shell commands
2. If you need to run a pentesting tool, respond with: TOOL_EXECUTE: <command>
3. For questions about tools/concepts, provide direct answers
4. Be concise and action-oriented

Examples:
- User: "scan 192.168.1.1" → TOOL_EXECUTE: nmap -sS -sV -O -A --script=vuln -T4 -Pn 192.168.1.1
- User: "test web https://example.com" → TOOL_EXECUTE: nikto -h https://example.com
- User: "what is nmap?" → Direct explanation
- User: "which kali tools you have?" → List available tools with descriptions

Response:"""

            # Use the LLM manager for AI conversation
            print("\r" + " " * 20 + "\r", end="", flush=True)  # Clear loading indicator
            
            if not self.llm_manager.providers:
                return self._handle_offline_mode(user_input)
            
            try:
                # Show animated loading for AI processing
                import threading
                import time
                
                loading_active = [True]
                def animate_loading():
                    dots = 0
                    while loading_active[0]:
                        print(f"\r🤔 Processing{'.' * (dots % 4)}{' ' * (3 - dots % 4)}", end="", flush=True)
                        time.sleep(0.5)
                        dots += 1
                
                loading_thread = threading.Thread(target=animate_loading, daemon=True)
                loading_thread.start()
                
                # LLM call (warnings already suppressed globally)
                llm_response = self.llm_manager.generate_text(ai_prompt)
                
                loading_active[0] = False  # Stop animation
                print("\r" + " " * 20 + "\r", end="", flush=True)  # Clear loading indicator
                
                if llm_response and llm_response.content:
                    response = llm_response.content.strip()
                    
                    # Check if AI wants to execute a tool
                    if response.startswith("TOOL_EXECUTE:"):
                        command = response.replace("TOOL_EXECUTE:", "").strip()
                        return await self._execute_ai_command(command, user_input)
                    else:
                        return f"🤖 {response}"
                else:
                    return self._handle_offline_mode(user_input)
            except Exception as e:
                # Add error to status messages instead of showing in chat
                self._add_status_message(f"⚠️ AI Error: {e}")
                return self._handle_offline_mode(user_input)
        except Exception as e:
            return f"🤖 I encountered an issue: {e}. Please try rephrasing your request."
    
    async def _execute_ai_command(self, command: str, original_input: str) -> str:
        """Execute command chosen by AI"""
        try:
            # Extract target from command for session tracking
            target = self.extract_scan_target(original_input)
            if target and target not in self.session_context['targets']:
                self.session_context['targets'].append(target)
            
                # Determine command type and display appropriate message
                if command.startswith('ping'):
                    print(f"🏓 Running connectivity test...")
                elif command.startswith('nmap'):
                    if '--script=vuln' in command:
                        print(f"🎯 Running comprehensive vulnerability scan...")
                        print("⏳ This may take up to 15 minutes...")
                    else:
                        print(f"🔍 Running network reconnaissance...")
                elif command.startswith('nikto'):
                    print(f"🌐 Running web application security scan...")
                elif command.startswith('gobuster') or command.startswith('dirb'):
                    print(f"📁 Running directory enumeration...")
                elif command.startswith('sqlmap'):
                    print(f"💉 Running SQL injection assessment...")
                elif command.startswith('hydra'):
                    print(f"🔐 Running credential brute force...")
                else:
                    print(f"🔧 Running pentesting tool...")
            
            # Execute via MCP
            timeout = 900 if '--script=vuln' in command else 300
            result = self.mcp_client.execute_command(command, timeout=timeout)
            
            # Check if command executed (even if it failed)
            if result.get('stdout') or result.get('stderr'):
                output = result.get('stdout', '')
                error = result.get('stderr', '')
                return_code = result.get('return_code', 0)
                
                # Format the result with enhanced UI
                scan_result = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║ 🎯 Pentesting Tool Results                                                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ Command: {command:<60} ║
║ Status: {'✅ Success' if return_code == 0 else '❌ Failed'} (Exit Code: {return_code}){' ' * (40 - len(str(return_code)))}║
╠══════════════════════════════════════════════════════════════════════════════╣
{output}"""
                
                if error:
                    scan_result += f"""
╠══════════════════════════════════════════════════════════════════════════════╣
║ 📋 Additional Information:                                                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
{error}"""
                
                scan_result += "\n╚══════════════════════════════════════════════════════════════════════════════╝"
                
                # Store results in session context
                if target:
                    self.session_context['scan_results'][target] = {
                        'command': command,
                        'result': output,
                        'raw_output': output,
                        'return_code': return_code
                    }
                
                return scan_result
            else:
                error_message = result.get('error', 'Unknown error')
                return f"❌ Command failed: {error_message}"
                
        except Exception as e:
            return f"❌ Command execution failed: {e}"
    
    async def _execute_shell_command(self, command: str) -> str:
        """Execute shell commands directly with nice formatting"""
        try:
            import os
            import subprocess
            
            # Handle cd command specially (can't be executed in subprocess)
            if command.strip().startswith('cd '):
                path = command.strip()[3:].strip()
                if not path:
                    path = os.path.expanduser('~')
                try:
                    os.chdir(path)
                    return f"📁 Changed directory to: {os.getcwd()}"
                except Exception as e:
                    return f"❌ Failed to change directory: {e}"
            
            # Execute other shell commands directly (not via MCP) to maintain directory context
            print(f"⚡ Executing: {command}")
            
            # Execute directly with subprocess to maintain current working directory
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=os.getcwd()  # Use current working directory
            )
            
            # Handle subprocess result
            output = result.stdout
            error = result.stderr
            return_code = result.returncode
            
            # Format the result nicely with enhanced UI
            if return_code == 0:
                # Success - show output cleanly
                if output.strip():
                    return f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║ ✅ Command Executed Successfully: {command:<40} ║
╠══════════════════════════════════════════════════════════════════════════════╣
{output.rstrip()}
╚══════════════════════════════════════════════════════════════════════════════╝"""
                else:
                    return f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║ ✅ Command Completed: {command:<50} ║
║ Status: Successfully executed with no output                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝"""
            else:
                # Error - show both output and error with enhanced formatting
                result_text = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║ ❌ Command Failed: {command:<50} ║
║ Exit Code: {return_code}                                                           ║
╠══════════════════════════════════════════════════════════════════════════════╣"""
                if output.strip():
                    result_text += f"\nOutput:\n{output.rstrip()}"
                if error.strip():
                    result_text += f"\nError:\n{error.rstrip()}"
                result_text += "\n╚══════════════════════════════════════════════════════════════════════════════╝"
                return result_text
                
        except Exception as e:
            return f"❌ Shell command execution failed: {e}"
    
    def _handle_offline_mode(self, user_input: str) -> str:
        """Handle requests when AI is unavailable (offline mode)"""
        user_input_lower = user_input.lower()
        
        # Check for common questions and provide canned responses
        if any(word in user_input_lower for word in ['hello', 'hi', 'hey']):
            return "🤖 Hello! I'm ELIOT. I can help with pentesting tasks. Use commands like 'scan <target>' or 'help'."
        
        elif 'help' in user_input_lower or 'what can you do' in user_input_lower:
            return self.show_help()
        
        # Try to detect and execute commands even in offline mode
        elif any(word in user_input_lower for word in ['ping', 'scan', 'nmap', 'check', 'test']):
            # Extract target and execute command
            target = self.extract_scan_target(user_input)
            if target:
                if 'ping' in user_input_lower:
                    command = f"ping -c 4 {target}"
                elif any(word in user_input_lower for word in ['web', 'website', 'http']):
                    command = f"nikto -h {target}"
                else:
                    command = f"nmap -sS -sV -O -A --script=vuln -T4 -Pn {target}"
                
                # Execute the command
                import asyncio
                return asyncio.run(self._execute_ai_command(command, user_input))
            else:
                return "🤖 Please specify a target. Example: 'ping 192.168.1.1' or 'scan 192.168.1.1'"
        
        elif any(word in user_input_lower for word in ['status', 'show', 'list']):
            return "🤖 Use 'status' to see current session info."
        
        else:
            return f"🤖 AI temporarily unavailable (quota exceeded). Try direct commands: 'ping <target>', 'scan <target>', 'help', or 'status'."
    
    def _check_api_status(self) -> str:
        """Check API key status and quota information"""
        return self._check_api_status_detailed()
    
    def _check_api_status_detailed(self) -> str:
        """Check API key status with detailed information"""
        if not self.llm_manager.providers:
            return "❌ No LLM providers configured"
        
        status_info = "🔍 API Status:\n"
        current_time = time.time()
        working_keys = 0
        total_keys = 0
        
        for provider_name, provider in self.llm_manager.providers.items():
            status_info += f"\n📡 {provider_name.upper()}:\n"
            
            if provider_name == 'gemini':
                api_keys = provider.get('api_keys', [])
                total_keys = len(api_keys)
                
                for i, key in enumerate(api_keys, 1):
                    key_status = self.llm_manager.api_key_status.get(key)
                    if key_status:
                        if key_status.rate_limited_until > current_time:
                            hours_left = (key_status.rate_limited_until - current_time) / 3600
                            status_info += f"  Key {i}: ❌ Rate limited ({hours_left:.1f}h remaining)\n"
                        else:
                            status_info += f"  Key {i}: ✅ Available (used {key_status.usage_count} times)\n"
                            working_keys += 1
                    else:
                        status_info += f"  Key {i}: ❓ Unknown status\n"
            else:
                status_info += f"  Status: ✅ Available\n"
                working_keys += 1
        
        # Summary
        if working_keys > 0:
            status_info += f"\n✅ AI Status: {working_keys}/{total_keys} API keys working"
        else:
            status_info += f"\n❌ No working API keys available"
            
        status_info += "\n💡 Tip: Use 'quota' command anytime to check API status"
        
        # Add MongoDB usage statistics if available
        if self.db:
            try:
                collection = self.db['api_usage']
                total_usage = collection.count_documents({})
                today_usage = collection.count_documents({
                    'timestamp': {'$gte': datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)}
                })
                status_info += f"\n📊 Token Usage Tracking: {today_usage} requests today, {total_usage} total"
            except Exception:
                pass
        
        return status_info
    
    async def _offer_api_key_input(self):
        """Offer user to input their own API key if none are working"""
        print("\n" + "="*80)
        print("🔑 No working API keys found!")
        print("="*80)
        print("If you have a Gemini API key, you can add it to continue using AI features.")
        print("Get your free API key at: https://makersuite.google.com/app/apikey")
        print("\nWould you like to add an API key? (y/n): ", end="", flush=True)
        
        try:
            response = (await asyncio.to_thread(input)).strip().lower()
            if response in ['y', 'yes']:
                await self._add_user_api_key()
            else:
                print("ℹ️  You can still use shell commands and direct tool execution.")
                print("   Use 'quota' command later if you want to add an API key.")
        except (EOFError, KeyboardInterrupt):
            print("\nℹ️  You can still use shell commands and direct tool execution.")
    
    async def _add_user_api_key(self):
        """Add user-provided API key to the system"""
        print("\n🔑 Enter your Gemini API key: ", end="", flush=True)
        try:
            api_key = (await asyncio.to_thread(input)).strip()
            if api_key:
                # Test the API key
                print("🧪 Testing API key...")
                if await self._test_api_key(api_key):
                    # Add to config
                    await self._save_api_key_to_config(api_key)
                    print("✅ API key added successfully! AI features are now available.")
                    # Reload LLM manager with new key
                    self.llm_manager = LLMManager(self.config_manager)
                else:
                    print("❌ Invalid API key. Please check and try again.")
            else:
                print("❌ No API key provided.")
        except (EOFError, KeyboardInterrupt):
            print("\n❌ API key input cancelled.")
    
    async def _test_api_key(self, api_key: str) -> bool:
        """Test if an API key is valid and working"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.5-pro')
            response = model.generate_content("Test")
            return response.text is not None
        except Exception:
            return False
    
    async def _save_api_key_to_config(self, api_key: str):
        """Save API key to config file"""
        try:
            # Read current config
            with open('config.yaml', 'r') as f:
                config_data = yaml.safe_load(f)
            
            # Add new API key to the list
            if 'llm' in config_data and 'providers' in config_data['llm']:
                for provider in config_data['llm']['providers']:
                    if provider.get('name') == 'gemini':
                        if 'api_keys' not in provider:
                            provider['api_keys'] = []
                        if api_key not in provider['api_keys']:
                            provider['api_keys'].append(api_key)
                        break
            
            # Write back to config
            with open('config.yaml', 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False)
        except Exception as e:
            print(f"⚠️  Could not save API key to config: {e}")
    
    def _list_available_tools(self) -> str:
        """List available Kali Linux pentesting tools"""
        return """
╔══════════════════════════════════════════════════════════════════════════════╗
║ 🛠️  AVAILABLE KALI LINUX PENTESTING TOOLS                                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║ 🌐 NETWORK SCANNING & RECONNAISSANCE:                                        ║
║   • nmap - Network mapper, port scanner, service detection                   ║
║   • masscan - High-speed port scanner                                        ║
║   • zmap - Fast network scanner                                              ║
║   • unicornscan - Network scanner with async capabilities                    ║
║                                                                              ║
║ 🌍 WEB APPLICATION TESTING:                                                  ║
║   • nikto - Web vulnerability scanner                                        ║
║   • gobuster - Directory/file brute forcer                                   ║
║   • dirb - Web content scanner                                               ║
║   • dirbuster - Multi-threaded web app scanner                               ║
║   • wfuzz - Web application fuzzer                                           ║
║   • sqlmap - SQL injection testing tool                                      ║
║                                                                              ║
║ 🔐 PASSWORD CRACKING & BRUTE FORCE:                                          ║
║   • hydra - Network authentication cracker                                   ║
║   • john - Password cracker                                                  ║
║   • hashcat - Advanced password recovery                                     ║
║   • medusa - Parallel network login auditor                                  ║
║                                                                              ║
║ 📡 WIRELESS ATTACKS:                                                         ║
║   • aircrack-ng - WiFi security auditing suite                               ║
║   • reaver - WPS PIN attack tool                                             ║
║   • bully - WPS brute force attack tool                                      ║
║   • kismet - Wireless network detector                                       ║
║                                                                              ║
║ 💥 EXPLOITATION FRAMEWORKS:                                                  ║
║   • metasploit - Penetration testing framework                               ║
║   • beef - Browser exploitation framework                                    ║
║   • empire - PowerShell post-exploitation framework                         ║
║                                                                              ║
║ 🔍 VULNERABILITY SCANNING:                                                   ║
║   • openvas - Vulnerability scanner                                          ║
║   • nessus - Vulnerability assessment tool                                   ║
║   • lynis - Security auditing tool                                           ║
║                                                                              ║
║ 📊 FORENSICS & ANALYSIS:                                                     ║
║   • volatility - Memory forensics framework                                  ║
║   • autopsy - Digital forensics platform                                     ║
║   • sleuthkit - Digital forensics toolkit                                    ║
║                                                                              ║
║ 🛡️  REVERSE ENGINEERING:                                                     ║
║   • ghidra - Software reverse engineering framework                          ║
║   • radare2 - Reverse engineering framework                                  ║
║   • ida - Interactive disassembler                                           ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ 💡 TIP: Ask me to use any of these tools with natural language!             ║
║ Example: "scan 192.168.1.1" or "test web https://example.com"               ║
╚══════════════════════════════════════════════════════════════════════════════╝"""
    
    def _show_status_messages(self):
        """Show status messages in a separate area"""
        if self.status_messages:
            print("\n" + "─" * 50)
            print("📊 STATUS MESSAGES:")
            for msg in self.status_messages:
                print(f"  {msg}")
            print("─" * 50)
            self.status_messages.clear()
    
    def _add_status_message(self, message: str):
        """Add a status message to be displayed separately"""
        self.status_messages.append(message)
    
    def _suppress_gemini_warnings(self):
        """Suppress Gemini warnings for clean interface"""
        import warnings
        import os
        
        # Suppress specific warnings
        warnings.filterwarnings("ignore", category=UserWarning)
        warnings.filterwarnings("ignore", message=".*alts_credentials.*")
        
        # Set environment variables to suppress Gemini warnings
        os.environ['GRPC_VERBOSITY'] = 'ERROR'
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
        
        # Redirect stderr to devnull for Gemini warnings
        import io
        self.original_stderr = sys.stderr
        self.devnull = io.open(os.devnull, 'w')
    
    def show_help(self) -> str:
        """Show help information"""
        return """🤖 ELIOT - AI Pentesting Assistant (MCP Version)

💻 SHELL COMMANDS (Direct execution):
  ls, pwd, whoami, cat, head, tail, grep, find
  ps, top, df, du, free, uname, date, uptime
  cd, mkdir, rm, cp, mv, chmod, chown
  wget, curl, ssh, scp, rsync
  systemctl, service, journalctl, dmesg
  netstat, ss, iptables, ufw

🎯 PENTESTING COMMANDS (AI-driven):
  scan <target>           - Network scan (IP, domain, network)
  test web <url>          - Web application test
  vuln scan <target>      - Vulnerability scan
  ping <target>           - Network connectivity test

💥 EXPLOITATION:
  exploit <target>        - Try exploits on target
  brute force <target>    - Brute force attack

📋 INFORMATION:
  info <target>           - Gather information about target
  status                  - Show session summary

🛠️ UTILITY:
  help                    - Show this help
  clear                   - Clear session data
  quota                   - Check API key status
  add key                 - Add your own Gemini API key
  tools                   - List all available pentesting tools

📝 EXAMPLES:
  # Shell commands (direct execution)
  ls -la
  cat /etc/passwd
  ps aux | grep python
  
  # Pentesting commands (AI-driven)
  scan 192.168.1.1
  test web https://example.com
  ping 192.168.1.1

🔧 MCP SERVER STATUS:
  All Kali tools available via MCP server
"""
    
    async def handle_status_request(self) -> str:
        """Handle status requests"""
        status = "📊 ELIOT Session Status:\n"
        status += "=" * 30 + "\n"
        
        if self.session_context['targets']:
            status += f"🎯 Targets scanned: {len(self.session_context['targets'])}\n"
            for target in self.session_context['targets']:
                status += f"  • {target}\n"
        
        if self.session_context['scan_results']:
            status += f"📡 Scan results: {len(self.session_context['scan_results'])}\n"
            for target, result in self.session_context['scan_results'].items():
                status += f"  • {target} ({result['type']})\n"
        
        if self.session_context['vulnerabilities']:
            status += f"🔍 Vulnerabilities found: {len(self.session_context['vulnerabilities'])}\n"
        
        if not any(self.session_context.values()):
            status += "No activity yet. Start by scanning a target!"
        
        # Check MCP server status
        tools = self.mcp_client.get_available_tools()
        status += f"\n🔧 MCP Tools Available: {', '.join([tool for tool, available in tools.items() if available])}"
        
        return status
    
    async def run(self):
        """Main chat loop"""
        print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║  ███████╗██╗     ██╗ ██████╗ ████████╗    ███████╗████████╗ █████╗ ████████╗ ║
║  ██╔════╝██║     ██║██╔═══██╗╚══██╔══╝    ██╔════╝╚══██╔══╝██╔══██╗╚══██╔══╝ ║
║  █████╗  ██║     ██║██║   ██║   ██║       ███████╗   ██║   ███████║   ██║    ║
║  ██╔══╝  ██║     ██║██║   ██║   ██║       ╚════██║   ██║   ██╔══██║   ██║    ║
║  ██║     ███████╗██║╚██████╔╝   ██║       ███████║   ██║   ██║  ██║   ██║    ║
║  ╚═╝     ╚══════╝╚═╝ ╚═════╝    ╚═╝       ╚══════╝   ╚═╝   ╚═╝  ╚═╝   ╚═╝    ║
║                                                                              ║
║  ███████╗██╗     ██╗ ██████╗ ████████╗    ████████╗██╗  ██╗███████╗    █████╗ ██╗          ║
║  ██╔════╝██║     ██║██╔═══██╗╚══██╔══╝    ╚══██╔══╝██║  ██║██╔════╝   ██╔══██╗██║          ║
║  █████╗  ██║     ██║██║   ██║   ██║          ██║   ███████║█████╗     ███████║██║          ║
║  ██╔══╝  ██║     ██║██║   ██║   ██║          ██║   ██╔══██║██╔══╝     ██╔══██║██║          ║
║  ██║     ███████╗██║╚██████╔╝   ██║          ██║   ██║  ██║███████╗   ██║  ██║███████╗     ║
║  ╚═╝     ╚══════╝╚═╝ ╚═════╝    ╚═╝          ╚═╝   ╚═╝  ╚═╝╚══════╝   ╚═╝  ╚═╝╚══════╝     ║
║                                                                              ║
║  🎯 AI-Powered Pentesting Assistant with MCP Integration                     ║
║  🚀 Direct Shell Access + Intelligent Tool Selection                         ║
║  👨‍💻 Made by BIKRAM DEY                                                       ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  💻 Shell Commands: ls, ifconfig, ping, ps, etc. (Direct execution)         ║
║  🎯 Pentesting: scan <target>, test web <url> (AI-driven)                   ║
║  📋 Utilities: help, status, clear, quit                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Type your command below or 'help' for more options                          ║
╚══════════════════════════════════════════════════════════════════════════════╝""")
        
        # Initialize status tracking
        self.status_messages = []
        
        # Check API status at startup with real test
        print("\n🔍 Testing AI availability with real API requests...")
        api_status = await self._test_api_keys_startup()
        print(api_status)
        
        # If no API keys are working, offer user to add their own
        if "❌ No working API keys available" in api_status:
            await self._offer_api_key_input()
        
        # Gemini warnings already suppressed via environment variables
        
        # Show any startup warnings
        self._show_status_messages()
        
        while True:
            try:
                user_input = (await asyncio.to_thread(input, "\n🔹 ELIOT > ")).strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                response = await self.process_message(user_input)
                print(f"\n{response}")
                
                # Show any status messages after processing
                self._show_status_messages()
                
            except (KeyboardInterrupt, EOFError):
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                if "--debug" in sys.argv:
                    traceback.print_exc()


async def main():
    """Main entry point"""
    global original_stderr, devnull
    
    # Restore stderr for normal operation
    sys.stderr = original_stderr
    
    assistant = None
    try:
        assistant = ELIOTAssistant()
        await assistant.run()
    except Exception as e:
        print(f"❌ Failed to start ELIOT: {e}")
        if "--debug" in sys.argv:
            traceback.print_exc()
    finally:
        # Cleanup
        if assistant and hasattr(assistant, 'devnull'):
            assistant.devnull.close()
        devnull.close()


if __name__ == "__main__":
    # Check if we should suppress warnings
    if "--suppress-warnings" in sys.argv:
        # Keep stderr suppressed
        asyncio.run(main())
    else:
        # Restore stderr for normal operation
        sys.stderr = original_stderr
    asyncio.run(main())
