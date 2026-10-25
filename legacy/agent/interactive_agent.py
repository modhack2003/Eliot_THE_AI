#!/usr/bin/env python3
"""
Interactive CLI Pentesting Agent using Gemini 2.5 Pro
Chat-based interface where user gives instructions and agent executes pentesting tasks
"""

import asyncio
import os
import re
import subprocess
import time
from typing import List, Dict, Any, Optional
from agent.llm_manager import LLMManager
from agent.tools.network_tools import NetworkTools
from agent.tools.vuln_scanner import VulnScanner
from agent.tools.exploit_tools import ExploitTools
from agent.tools.web_tools import WebTools
from agent.tools.password_tools import PasswordTools
from agent.config_manager import ConfigManager

class InteractivePentestingAgent:
    def __init__(self):
        self.config = ConfigManager()
        self.llm_manager = LLMManager(self.config)
        self.network_tools = NetworkTools()
        self.vuln_scanner = VulnScanner()
        self.exploit_tools = ExploitTools()
        self.web_tools = WebTools()
        self.password_tools = PasswordTools()
        
        self.targets = []
        self.session_context = {}
        self.conversation_history = []
        self.current_targets = []
        
    async def start_chat(self):
        """Start interactive chat session"""
        print("\n" + "-" * 80)
        print("ELIOT - HACKER ASSISTANT by Bikram@2003")
        print("-" * 80)
        print("[INFO] Type 'help' for commands | Type 'quit', 'exit', or 'bye' to exit")
        print("[INFO] I can help you with network scanning, vulnerability assessment,")
        print("[INFO] exploitation, and more. Just tell me what you want to do!")
        print("-" * 80)
        
        # Initial greeting
        greeting = await self.get_gemini_response(
            "You are an AI pentesting assistant. Greet the user warmly and explain that you can help with network scanning, vulnerability assessment, exploitation, and other pentesting tasks. Keep it brief and professional."
        )
        print(f"\n[AI] Assistant: {greeting}\n")
        
        while True:
            try:
                try:
                    user_input = input("[USER] You: ").strip()
                except EOFError:
                    print("\nAssistant: Input stream closed. Exiting...")
                    break
                except KeyboardInterrupt:
                    print("\nAssistant: Goodbye! Remember to stay ethical in your testing.")
                    break
                
                if user_input.lower() in ['quit', 'exit', 'q', 'bye', 'goodbye', 'stop']:
                    print("\n[AI] Assistant: Goodbye! Remember to stay ethical in your testing.")
                    break
                
                if user_input.lower() == 'help':
                    self.show_help()
                    continue
                
                if not user_input:
                    continue
                
                # Process command
                response = await self.process_user_input(user_input)
                print(f"\n[AI] Assistant: {response}\n")
                
                # Store in conversation history
                self.conversation_history.append({
                    "user": user_input,
                    "assistant": response,
                    "timestamp": asyncio.get_event_loop().time()
                })
                
            except KeyboardInterrupt:
                print("\nAssistant: Goodbye! Remember to stay ethical in your testing.")
                break
            except Exception as e:
                print(f"Assistant: Sorry, I encountered an error: {e}")
    
    async def process_user_input(self, user_input: str) -> str:
        """Process user input and generate response"""
        
        # Check for specific commands first
        if self.is_scan_command(user_input):
            return await self.handle_scan_command(user_input)
        elif self.is_exploit_command(user_input):
            return await self.handle_exploit_command(user_input)
        elif self.is_vuln_check_command(user_input):
            return await self.handle_vuln_check_command(user_input)
        elif self.is_web_test_command(user_input):
            return await self.handle_web_test_command(user_input)
        elif self.is_password_crack_command(user_input):
            return await self.handle_password_crack_command(user_input)
        elif self.is_ping_command(user_input):
            return await self.handle_ping_command(user_input)
        elif self.is_gateway_command(user_input):
            return await self.handle_gateway_command(user_input)
        elif self.is_autonomous_switch_command(user_input):
            return await self.handle_autonomous_switch(user_input)
        else:
            # Use Gemini for general conversation and analysis
            return await self.get_gemini_response_with_context(user_input)
    
    async def get_gemini_response_with_context(self, user_input: str) -> str:
        """Get response from Gemini with conversation context"""
        context = f"""
        Conversation history: {self.conversation_history[-3:] if self.conversation_history else "None"}
        Current targets: {self.current_targets}
        Available tools: nmap, metasploit, sqlmap, hydra, john, hashcat, gobuster, dirb, nikto, ping, gateway detection
        
        User input: {user_input}
        
        You are an AI pentesting assistant. Analyze the user's request and:
        1. If they want to perform pentesting tasks, DO NOT just give instructions - instead suggest the specific command they should use with this agent
        2. If they ask questions about pentesting, provide helpful answers
        3. If they need guidance on tools or techniques, offer detailed explanations
        4. Always be professional, ethical, and helpful
        5. Tell them the exact command to use with this agent (like "find gateway", "ping 8.8.8.8", "scan 192.168.1.0/24")
        6. Do NOT provide manual command instructions - direct them to use this agent's built-in commands
        
        IMPORTANT: This agent has built-in commands that automatically execute tools. Don't tell them to run commands manually - tell them what command to use with this agent.
        """
        
        return await self.get_gemini_response(context)
    
    async def get_gemini_response(self, prompt: str) -> str:
        """Get response from Gemini"""
        try:
            response = self.llm_manager.generate_response(prompt, provider="gemini")
            if response and response.strip():
                return response.strip()
            else:
                return "I'm having trouble getting a response from Gemini. This might be a temporary issue with the API."
        except Exception as e:
            return f"I encountered an error while communicating with Gemini: {str(e)}. Please try again or check your API keys."
    
    def is_scan_command(self, text: str) -> bool:
        """Check if input is a scan command"""
        scan_keywords = ['scan', 'nmap', 'discover', 'find targets', 'network scan']
        return any(keyword in text.lower() for keyword in scan_keywords)
    
    def is_exploit_command(self, text: str) -> bool:
        """Check if input is an exploit command"""
        exploit_keywords = ['exploit', 'attack', 'metasploit', 'msfconsole', 'payload']
        return any(keyword in text.lower() for keyword in exploit_keywords)
    
    def is_vuln_check_command(self, text: str) -> bool:
        """Check if input is a vulnerability check command"""
        vuln_keywords = ['vulnerability', 'vuln', 'check vuln', 'cve', 'security scan']
        return any(keyword in text.lower() for keyword in vuln_keywords)
    
    def is_web_test_command(self, text: str) -> bool:
        """Check if input is a web testing command"""
        web_keywords = ['web', 'sql injection', 'xss', 'web scan', 'http', 'https']
        return any(keyword in text.lower() for keyword in web_keywords)
    
    def is_password_crack_command(self, text: str) -> bool:
        """Check if input is a password cracking command"""
        pass_keywords = ['password', 'brute force', 'crack', 'hydra', 'john', 'hashcat']
        return any(keyword in text.lower() for keyword in pass_keywords)
    
    def is_ping_command(self, text: str) -> bool:
        """Check if input is a ping command"""
        ping_keywords = ['ping', 'ping -c', 'ping -n']
        return any(keyword in text.lower() for keyword in ping_keywords)
    
    def is_gateway_command(self, text: str) -> bool:
        """Check if input is a gateway detection command"""
        gateway_keywords = ['gateway', 'default gateway', 'router', 'lan gateway', 'find gateway', 'get gateway']
        return any(keyword in text.lower() for keyword in gateway_keywords)
    
    def is_autonomous_switch_command(self, text: str) -> bool:
        """Check if input is a command to switch to autonomous mode"""
        autonomous_keywords = [
            'do anything', 'break into', 'hack everything', 'autonomous mode',
            'full attack', 'no limits', 'go autonomous', 'attack mode',
            'unleash', 'destroy', 'compromise', 'penetrate everything'
        ]
        return any(keyword in text.lower() for keyword in autonomous_keywords)
    
    async def handle_scan_command(self, command: str) -> str:
        """Handle network scanning commands"""
        # Extract target from command
        targets = self.extract_targets(command)
        
        if not targets:
            return "Please specify a target to scan. Example: 'scan 192.168.1.0/24' or 'scan 192.168.1.100'"
        
        result = "Starting network scan...\n"
        
        for target in targets:
            try:
                result += f"\nScanning {target}:\n"
                
                # Run basic nmap scan
                scan_result = await self.network_tools.scan_host(target)
                result += f"Basic scan result: {scan_result}\n"
                
                # Add to current targets
                if target not in self.current_targets:
                    self.current_targets.append(target)
                
            except Exception as e:
                result += f"Error scanning {target}: {e}\n"
        
        result += "\nScan completed. You can now run vulnerability checks or exploitation attempts."
        return result
    
    async def handle_exploit_command(self, command: str) -> str:
        """Handle exploitation commands"""
        targets = self.extract_targets(command)
        
        if not targets:
            if not self.current_targets:
                return "No targets available. Please scan for targets first or specify targets in your command."
            targets = self.current_targets
        
        result = "Starting exploitation attempts...\n"
        
        for target in targets:
            try:
                result += f"\nAttempting to exploit {target}:\n"
                
                # Run vulnerability scan first
                vulns = await self.vuln_scanner.scan_target(target)
                result += f"Found vulnerabilities: {vulns}\n"
                
                # Attempt exploitation based on vulnerabilities
                exploit_result = await self.exploit_tools.exploit_target(target, vulns)
                result += f"Exploitation result: {exploit_result}\n"
                
            except Exception as e:
                result += f"Error exploiting {target}: {e}\n"
        
        return result
    
    async def handle_vuln_check_command(self, command: str) -> str:
        """Handle vulnerability checking commands"""
        targets = self.extract_targets(command)
        
        if not targets:
            if not self.current_targets:
                return "No targets available. Please scan for targets first or specify targets in your command."
            targets = self.current_targets
        
        result = "Running vulnerability assessment...\n"
        
        for target in targets:
            try:
                result += f"\nChecking vulnerabilities on {target}:\n"
                
                vulns = await self.vuln_scanner.scan_target(target)
                result += f"Vulnerabilities found: {vulns}\n"
                
            except Exception as e:
                result += f"Error checking vulnerabilities on {target}: {e}\n"
        
        return result
    
    async def handle_web_test_command(self, command: str) -> str:
        """Handle web testing commands"""
        targets = self.extract_targets(command)
        
        if not targets:
            return "Please specify a web target to test. Example: 'test web http://192.168.1.100'"
        
        result = "Starting web application testing...\n"
        
        for target in targets:
            try:
                result += f"\nTesting web application at {target}:\n"
                
                # Run web vulnerability scan
                web_result = await self.web_tools.scan_web_app(target)
                result += f"Web scan result: {web_result}\n"
                
            except Exception as e:
                result += f"Error testing web app at {target}: {e}\n"
        
        return result
    
    async def handle_password_crack_command(self, command: str) -> str:
        """Handle password cracking commands"""
        result = "Password cracking functionality available. Please specify:\n"
        result += "- Target service (SSH, FTP, HTTP, etc.)\n"
        result += "- Target IP address\n"
        result += "- Username (optional)\n"
        result += "Example: 'brute force SSH 192.168.1.100 admin'"
        return result
    
    async def handle_ping_command(self, command: str) -> str:
        """Handle ping commands"""
        import subprocess
        import re
        
        # Extract target from command
        targets = self.extract_targets(command)
        
        if not targets:
            return "Please specify a target to ping. Example: 'ping google.com' or 'ping 8.8.8.8'"
        
        # Extract number of pings if specified
        ping_count = 4  # default
        count_match = re.search(r'(\d+)\s*times?', command.lower())
        if count_match:
            ping_count = int(count_match.group(1))
        
        result = f"Pinging {targets[0]} {ping_count} times...\n\n"
        
        try:
            # Run ping command
            if os.name == 'nt':  # Windows
                cmd = ['ping', '-n', str(ping_count), targets[0]]
            else:  # Linux/Mac
                cmd = ['ping', '-c', str(ping_count), targets[0]]
            
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if process.returncode == 0:
                result += process.stdout
                result += f"\n[SUCCESS] Ping completed successfully!"
            else:
                result += f"[ERROR] Ping failed with return code {process.returncode}\n"
                result += f"Error: {process.stderr}"
                
        except subprocess.TimeoutExpired:
            result += "[ERROR] Ping command timed out"
        except Exception as e:
            result += f"[ERROR] Failed to execute ping: {e}"
        
        return result
    
    async def handle_gateway_command(self, command: str) -> str:
        """Handle gateway detection commands"""
        import subprocess
        import platform
        
        result = "Detecting your LAN gateway...\n\n"
        
        try:
            system = platform.system().lower()
            
            if system == "windows":
                # Windows: use ipconfig and parse output
                process = subprocess.run(['ipconfig'], capture_output=True, text=True, timeout=10)
                
                if process.returncode == 0:
                    output = process.stdout
                    result += "Windows Gateway Detection Results:\n"
                    result += "-" * 50 + "\n"
                    
                    # Look for default gateway in output
                    lines = output.split('\n')
                    gateway_found = False
                    
                    for line in lines:
                        if 'default gateway' in line.lower():
                            gateway_found = True
                            result += f"Gateway: {line.strip()}\n"
                    
                    if not gateway_found:
                        result += "No default gateway found in ipconfig output.\n"
                        result += "Full ipconfig output:\n"
                        result += output
                    
                    # Also try route command for more details
                    result += "\nDetailed routing information:\n"
                    result += "-" * 30 + "\n"
                    try:
                        route_process = subprocess.run(['route', 'print'], capture_output=True, text=True, timeout=10)
                        if route_process.returncode == 0:
                            result += route_process.stdout
                    except:
                        result += "Could not retrieve detailed routing table.\n"
                        
                else:
                    result += f"Error running ipconfig: {process.stderr}"
                    
            elif system in ["linux", "darwin"]:  # Linux or macOS
                # Linux/macOS: use ip route or route command
                result += f"{system.title()} Gateway Detection Results:\n"
                result += "-" * 50 + "\n"
                
                # Try modern ip command first
                try:
                    ip_process = subprocess.run(['ip', 'route', 'show', 'default'], capture_output=True, text=True, timeout=10)
                    if ip_process.returncode == 0 and ip_process.stdout.strip():
                        result += "Default Gateway (ip route):\n"
                        result += ip_process.stdout
                    else:
                        raise Exception("ip command failed")
                except:
                    # Fallback to traditional route command
                    try:
                        route_process = subprocess.run(['route', '-n'], capture_output=True, text=True, timeout=10)
                        if route_process.returncode == 0:
                            result += "Routing Table (route -n):\n"
                            result += route_process.stdout
                    except:
                        result += "Could not detect gateway using standard commands.\n"
                
                # Also try netstat for additional info
                try:
                    netstat_process = subprocess.run(['netstat', '-rn'], capture_output=True, text=True, timeout=10)
                    if netstat_process.returncode == 0:
                        result += "\nNetstat Routing Table:\n"
                        result += "-" * 30 + "\n"
                        result += netstat_process.stdout
                except:
                    pass
                    
            else:
                result += f"Unsupported operating system: {system}\n"
                result += "Please run manually:\n"
                result += "- Windows: ipconfig\n"
                result += "- Linux: ip route show default\n"
                result += "- macOS: route -n get default\n"
                
        except subprocess.TimeoutExpired:
            result += "[ERROR] Gateway detection timed out"
        except Exception as e:
            result += f"[ERROR] Failed to detect gateway: {e}"
        
        result += "\n\n[INFO] Next steps you might want to try:\n"
        result += "* Scan the gateway for open ports: 'scan [gateway_ip]'\n"
        result += "* Check if it has a web interface: 'test web http://[gateway_ip]'\n"
        result += "* Look for common router vulnerabilities\n"
        
        return result
    
    async def handle_autonomous_switch(self, command: str) -> str:
        """Handle switching to autonomous mode"""
        import subprocess
        import sys
        
        result = "WARNING: SWITCHING TO AUTONOMOUS MODE\n"
        result += "=" * 50 + "\n"
        result += "The autonomous agent will:\n"
        result += "* Operate without human oversight\n"
        result += "* Automatically discover and attack targets\n"
        result += "* Never ask for permission\n"
        result += "* Use all available techniques\n"
        result += "* Continue until manually stopped\n\n"
        
        # Save current session data
        session_data = {
            'current_targets': self.current_targets,
            'conversation_history': self.conversation_history[-5:],  # Last 5 exchanges
            'session_context': self.session_context,
            'timestamp': time.time()
        }
        
        # Write session data to file for autonomous agent
        try:
            import json
            with open('autonomous_handoff.json', 'w') as f:
                json.dump(session_data, f, indent=2)
            result += "[INFO] Session data saved for autonomous agent\n"
        except Exception as e:
            result += f"[WARNING] Could not save session data: {e}\n"
        
        result += "\nStarting autonomous agent in 5 seconds...\n"
        result += "Press Ctrl+C to cancel\n"
        
        # Countdown
        for i in range(5, 0, -1):
            result += f"{i}... "
            time.sleep(1)
        
        result += "\n[LAUNCHING] Starting autonomous agent...\n"
        
        # Launch autonomous agent
        try:
            # Use subprocess to start main.py
            subprocess.Popen([sys.executable, 'main.py'], 
                           cwd=os.getcwd(),
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE)
            
            result += "[SUCCESS] Autonomous agent started!\n"
            result += "This interactive session will now exit.\n"
            
        except Exception as e:
            result += f"[ERROR] Failed to start autonomous agent: {e}\n"
            result += "Please run 'python3 main.py' manually\n"
        
        return result
    
    def extract_targets(self, command: str) -> List[str]:
        """Extract IP addresses or hostnames from command"""
        # Regex patterns for IP addresses and CIDR notation
        ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?:/[0-9]{1,2})?\b'
        hostname_pattern = r'\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
        
        targets = re.findall(ip_pattern, command)
        targets.extend(re.findall(hostname_pattern, command))
        
        return list(set(targets))  # Remove duplicates
    
    def show_help(self):
        """Show available commands"""
        help_text = """
================================================================================
                           AVAILABLE COMMANDS                                    
================================================================================

  NETWORK SCANNING:                                                            
  * "scan 192.168.1.0/24" - Scan network range                                
  * "scan 192.168.1.100" - Scan single target                                 
  * "discover hosts on 192.168.1.0/24" - Host discovery                       
  * "ping google.com" - Ping a host                                            
  * "ping 8.8.8.8 4 times" - Ping with specific count                         
  * "find gateway" - Detect LAN gateway/router IP                              
  * "get gateway" - Find default gateway                         

  VULNERABILITY ASSESSMENT:                                                    
  * "check vulnerabilities 192.168.1.100" - Run vulnerability scan            
  * "vuln scan 192.168.1.100" - Vulnerability assessment                      
  * "security scan 192.168.1.100" - Comprehensive security scan               

  EXPLOITATION:                                                                
  * "exploit 192.168.1.100" - Attempt to exploit target                       
  * "attack 192.168.1.100" - Launch attack against target                     
  * "metasploit 192.168.1.100" - Use Metasploit against target                

  WEB APPLICATION TESTING:                                                     
  * "test web http://192.168.1.100" - Web application testing                 
  * "sql injection test http://192.168.1.100/login" - SQL injection test      
  * "web scan http://192.168.1.100" - Web vulnerability scan                  

  PASSWORD CRACKING:                                                           
  * "brute force SSH 192.168.1.100" - SSH brute force                         
  * "crack passwords 192.168.1.100" - Password cracking                       
  * "hydra SSH 192.168.1.100" - Hydra SSH attack                              

  GENERAL:                                                                     
  * "help" - Show this help                                                    
  * "quit", "exit", "bye" - Exit the assistant                                 

  AUTONOMOUS MODE:                                                             
  * "do anything" - Switch to fully autonomous mode                            
  * "break into system" - Launch autonomous attack agent                       
  * "autonomous mode" - Start unsupervised pentesting                          
  * "full attack" - Deploy autonomous agent (DANGEROUS!)                                 

  CONVERSATION EXAMPLES:                                                       
  * "I found a Windows machine at 192.168.1.100, what should I do?"           
  * "Scan my local network and find web servers"                              
  * "How do I test for SQL injection?"                                        
  * "What vulnerabilities should I look for on this Linux server?"            

================================================================================
"""
        print(help_text)
