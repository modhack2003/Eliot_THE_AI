"""
Target profiling system for building detailed profiles of discovered systems
"""

import asyncio
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import re
import json

from ..tools.network_tools import network_tools
from ..tools.vuln_scanner import vuln_scanner
from ..tools.web_tools import web_tools
from ..persistence.database import get_database, Target, Experience
from ..persistence.logger import get_action_logger


@dataclass
class ServiceProfile:
    """Profile of a service running on target"""
    port: int
    protocol: str
    service_name: str
    version: Optional[str] = None
    banner: Optional[str] = None
    vulnerabilities: List[Dict[str, Any]] = None
    web_technologies: Dict[str, str] = None
    web_directories: List[str] = None
    
    def __post_init__(self):
        if self.vulnerabilities is None:
            self.vulnerabilities = []
        if self.web_technologies is None:
            self.web_technologies = {}
        if self.web_directories is None:
            self.web_directories = []


@dataclass
class TargetProfile:
    """Complete profile of a target system"""
    ip: str
    hostname: Optional[str] = None
    os: Optional[str] = None
    os_version: Optional[str] = None
    architecture: Optional[str] = None
    services: List[ServiceProfile] = None
    vulnerabilities: List[Dict[str, Any]] = None
    network_info: Dict[str, Any] = None
    web_applications: List[Dict[str, Any]] = None
    priority_score: int = 1
    last_profiled: float = None
    
    def __post_init__(self):
        if self.services is None:
            self.services = []
        if self.vulnerabilities is None:
            self.vulnerabilities = []
        if self.network_info is None:
            self.network_info = {}
        if self.web_applications is None:
            self.web_applications = []
        if self.last_profiled is None:
            self.last_profiled = time.time()


class TargetProfiler:
    """Builds detailed profiles of discovered targets"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("target_profiler")
        self.action_logger = get_action_logger()
        self.db = None
        self.profiling_queue = asyncio.Queue()
        self.running = False
    
    async def initialize(self):
        """Initialize the profiler"""
        self.db = await get_database()
        self.logger.info("Target profiler initialized")
    
    async def start_profiling(self):
        """Start target profiling"""
        self.running = True
        self.logger.info("Starting target profiling")
        
        # Start profiling worker
        asyncio.create_task(self._profiling_worker())
        
        # Start queue processor
        asyncio.create_task(self._process_profiling_queue())
    
    async def stop_profiling(self):
        """Stop target profiling"""
        self.running = False
        self.logger.info("Stopping target profiling")
    
    async def profile_target(self, ip: str, priority: int = 1):
        """Schedule a target for profiling"""
        try:
            # Check if target exists
            target = await self.db.get_target(ip)
            if not target:
                self.logger.warning(f"Target {ip} not found in database")
                return
            
            # Add to profiling queue
            profile_job = {
                "ip": ip,
                "priority": priority,
                "timestamp": time.time()
            }
            await self.profiling_queue.put(profile_job)
            
            self.logger.info(f"Scheduled profiling for target: {ip}")
            
        except Exception as e:
            self.logger.error(f"Failed to schedule profiling for {ip}: {e}")
    
    async def _process_profiling_queue(self):
        """Process the profiling queue"""
        while self.running:
            try:
                # Get next profiling job
                profile_job = await self.profiling_queue.get()
                
                # Execute profiling
                await self._execute_profiling_job(profile_job)
                
                # Mark task as done
                self.profiling_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Profiling queue processing error: {e}")
                await asyncio.sleep(5)
    
    async def _execute_profiling_job(self, profile_job: Dict[str, Any]):
        """Execute a profiling job"""
        try:
            ip = profile_job["ip"]
            self.logger.info(f"Profiling target: {ip}")
            
            start_time = time.time()
            
            # Build comprehensive profile
            profile = await self._build_target_profile(ip)
            
            duration = time.time() - start_time
            
            # Store profile
            await self._store_target_profile(profile)
            
            # Log profiling
            self.action_logger.log_discovery(
                ip,
                "profiling",
                {
                    "success": True,
                    "services_found": len(profile.services),
                    "vulnerabilities_found": len(profile.vulnerabilities),
                    "duration": duration
                }
            )
            
            # Store experience
            experience = Experience(
                target=ip,
                action="profiling",
                tool_used="target_profiler",
                success=True,
                timestamp=time.time(),
                context={"profile_job": profile_job},
                result={
                    "services": len(profile.services),
                    "vulnerabilities": len(profile.vulnerabilities),
                    "duration": duration
                }
            )
            await self.db.store_experience(experience)
            
        except Exception as e:
            self.logger.error(f"Failed to profile target {ip}: {e}")
    
    async def _build_target_profile(self, ip: str) -> TargetProfile:
        """Build comprehensive target profile"""
        profile = TargetProfile(ip=ip)
        
        # Get basic target info from database
        target = await self.db.get_target(ip)
        if target:
            profile.hostname = target.hostname
            profile.services = [ServiceProfile(**service) for service in target.services]
        
        # Network information
        profile.network_info = await self._get_network_info(ip)
        
        # OS detection
        await self._detect_os(profile)
        
        # Service profiling
        await self._profile_services(profile)
        
        # Vulnerability scanning
        await self._scan_vulnerabilities(profile)
        
        # Web application detection
        await self._detect_web_applications(profile)
        
        # Calculate priority score
        profile.priority_score = self._calculate_priority_score(profile)
        
        return profile
    
    async def _get_network_info(self, ip: str) -> Dict[str, Any]:
        """Get network information for target"""
        try:
            network_info = network_tools.get_network_info(ip)
            return network_info
        except Exception as e:
            self.logger.error(f"Failed to get network info for {ip}: {e}")
            return {}
    
    async def _detect_os(self, profile: TargetProfile):
        """Detect operating system"""
        try:
            # Use nmap for OS detection
            os_scan_result = network_tools.nmap_script_scan(
                profile.ip, 
                "osdetect"
            )
            
            if os_scan_result.get("success", False):
                output = os_scan_result.get("output", "")
                
                # Parse OS information from nmap output
                os_match = re.search(r'Running: ([^\n]+)', output)
                if os_match:
                    profile.os = os_match.group(1).strip()
                
                # Parse OS version
                version_match = re.search(r'OS details: ([^\n]+)', output)
                if version_match:
                    profile.os_version = version_match.group(1).strip()
                
                # Parse architecture
                arch_match = re.search(r'Architecture: ([^\n]+)', output)
                if arch_match:
                    profile.architecture = arch_match.group(1).strip()
            
        except Exception as e:
            self.logger.error(f"OS detection failed for {profile.ip}: {e}")
    
    async def _profile_services(self, profile: TargetProfile):
        """Profile services running on target"""
        try:
            for service in profile.services:
                # Get service banner
                if service.port in [80, 443, 8080, 8443]:
                    # Web service profiling
                    await self._profile_web_service(profile, service)
                elif service.port in [21, 22, 23, 25, 110, 143, 993, 995]:
                    # Common service profiling
                    await self._profile_common_service(profile, service)
        
        except Exception as e:
            self.logger.error(f"Service profiling failed for {profile.ip}: {e}")
    
    async def _profile_web_service(self, profile: TargetProfile, service: ServiceProfile):
        """Profile web services"""
        try:
            protocol = "https" if service.port in [443, 8443] else "http"
            url = f"{protocol}://{profile.ip}:{service.port}"
            
            # Technology detection
            technologies = web_tools.whatweb_scan(url)
            service.web_technologies = technologies
            
            # Directory enumeration
            directories = web_tools.dirb_scan(url)
            service.web_directories = [d.url for d in directories]
            
            # Vulnerability scanning
            vulnerabilities = web_tools.nikto_scan(profile.ip, service.port)
            service.vulnerabilities = [vuln.__dict__ for vuln in vulnerabilities]
            
        except Exception as e:
            self.logger.error(f"Web service profiling failed for {profile.ip}:{service.port}: {e}")
    
    async def _profile_common_service(self, profile: TargetProfile, service: ServiceProfile):
        """Profile common services"""
        try:
            # Use nmap scripts for service-specific profiling
            script_map = {
                21: "ftp-anon,ftp-bounce,ftp-libopie,ftp-proftpd-backdoor,ftp-vsftpd-backdoor,ftp-vuln-cve2010-4221",
                22: "ssh-hostkey,sshv1,ssh2-enum-algos",
                23: "telnet-encryption,telnet-ntlm-info",
                25: "smtp-commands,smtp-enum-users,smtp-vuln-cve2010-4344,smtp-vuln-cve2011-1720,smtp-vuln-cve2011-1764",
                110: "pop3-brute,pop3-capabilities,pop3-ntlm-info",
                143: "imap-capabilities,imap-ntlm-info",
                993: "imap-capabilities,imap-ntlm-info",
                995: "pop3-brute,pop3-capabilities,pop3-ntlm-info"
            }
            
            if service.port in script_map:
                scripts = script_map[service.port]
                scan_result = network_tools.nmap_script_scan(profile.ip, scripts)
                
                if scan_result.get("success", False):
                    # Parse vulnerabilities from scan output
                    vulnerabilities = self._parse_nmap_vulnerabilities(scan_result.get("output", ""))
                    service.vulnerabilities.extend(vulnerabilities)
        
        except Exception as e:
            self.logger.error(f"Common service profiling failed for {profile.ip}:{service.port}: {e}")
    
    def _parse_nmap_vulnerabilities(self, output: str) -> List[Dict[str, Any]]:
        """Parse vulnerabilities from nmap output"""
        vulnerabilities = []
        
        for line in output.split('\n'):
            if '|' in line and ('VULNERABLE' in line or 'SAFE' in line):
                if 'VULNERABLE' in line:
                    vuln_info = line.split('|')[1].strip()
                    vuln = {
                        "name": vuln_info,
                        "severity": "unknown",
                        "description": vuln_info
                    }
                    vulnerabilities.append(vuln)
        
        return vulnerabilities
    
    async def _scan_vulnerabilities(self, profile: TargetProfile):
        """Perform vulnerability scanning"""
        try:
            # Use vuln_scanner for comprehensive vulnerability scanning
            vuln_result = vuln_scanner.comprehensive_vuln_scan(profile.ip)
            
            profile.vulnerabilities = [vuln.__dict__ for vuln in vuln_result.vulnerabilities]
            
        except Exception as e:
            self.logger.error(f"Vulnerability scanning failed for {profile.ip}: {e}")
    
    async def _detect_web_applications(self, profile: TargetProfile):
        """Detect web applications"""
        try:
            web_ports = [80, 443, 8080, 8443, 8000, 8008, 8081, 8443]
            web_services = [s for s in profile.services if s.port in web_ports]
            
            for service in web_services:
                protocol = "https" if service.port in [443, 8443] else "http"
                url = f"{protocol}://{profile.ip}:{service.port}"
                
                # Comprehensive web scan
                web_scan_result = web_tools.comprehensive_web_scan(url)
                
                web_app = {
                    "url": url,
                    "port": service.port,
                    "technologies": service.web_technologies,
                    "directories": service.web_directories,
                    "vulnerabilities": [vuln.__dict__ for vuln in web_scan_result.vulnerabilities]
                }
                
                profile.web_applications.append(web_app)
        
        except Exception as e:
            self.logger.error(f"Web application detection failed for {profile.ip}: {e}")
    
    def _calculate_priority_score(self, profile: TargetProfile) -> int:
        """Calculate priority score for target"""
        score = 1
        
        # Higher score for more services
        score += len(profile.services) * 2
        
        # Higher score for web applications
        score += len(profile.web_applications) * 5
        
        # Higher score for vulnerabilities
        score += len(profile.vulnerabilities) * 3
        
        # Higher score for high-value services
        high_value_ports = [22, 23, 80, 443, 3389, 5900, 1433, 3306, 5432]
        for service in profile.services:
            if service.port in high_value_ports:
                score += 5
        
        # Higher score for compromised systems
        if profile.vulnerabilities:
            high_severity_vulns = [v for v in profile.vulnerabilities 
                                 if v.get("severity", "").lower() in ["high", "critical"]]
            score += len(high_severity_vulns) * 10
        
        return min(score, 100)  # Cap at 100
    
    async def _store_target_profile(self, profile: TargetProfile):
        """Store target profile in database"""
        try:
            # Update target with profile information
            target = await self.db.get_target(profile.ip)
            if target:
                target.hostname = profile.hostname
                target.os = profile.os
                target.services = [service.__dict__ for service in profile.services]
                target.vulnerabilities = profile.vulnerabilities
                target.last_seen = time.time()
                
                await self.db.store_target(target)
            
            self.logger.info(f"Stored profile for target: {profile.ip} (priority: {profile.priority_score})")
            
        except Exception as e:
            self.logger.error(f"Failed to store profile for {profile.ip}: {e}")
    
    async def get_high_priority_targets(self, limit: int = 10) -> List[Target]:
        """Get high priority targets"""
        try:
            targets = await self.db.get_all_targets()
            
            # Sort by priority (we'll use service count as proxy for priority)
            targets.sort(key=lambda t: len(t.services), reverse=True)
            
            return targets[:limit]
            
        except Exception as e:
            self.logger.error(f"Failed to get high priority targets: {e}")
            return []
    
    async def _profiling_worker(self):
        """Background profiling worker"""
        while self.running:
            try:
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.error(f"Profiling worker error: {e}")
                await asyncio.sleep(5)


# Global profiler instance
profiler_instance = None


async def get_profiler(config) -> TargetProfiler:
    """Get or create profiler instance"""
    global profiler_instance
    
    if profiler_instance is None:
        profiler_instance = TargetProfiler(config)
        await profiler_instance.initialize()
    
    return profiler_instance
