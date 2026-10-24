"""
Web testing tools wrapper for Kali Linux
"""

import subprocess
import json
import re
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class WebVulnerability:
    """Represents a web vulnerability"""
    name: str
    severity: str
    url: str
    parameter: Optional[str] = None
    description: Optional[str] = None
    payload: Optional[str] = None


@dataclass
class DirectoryResult:
    """Result of directory enumeration"""
    url: str
    status_code: int
    content_length: int
    content_type: Optional[str] = None


@dataclass
class WebScanResult:
    """Result of web scanning"""
    target: str
    vulnerabilities: List[WebVulnerability]
    directories: List[DirectoryResult]
    scan_type: str
    timestamp: float


class WebTools:
    """Wrapper for web testing tools"""
    
    def __init__(self):
        self.logger = logging.getLogger("web_tools")
        self.executor = ThreadPoolExecutor(max_workers=5)
    
    def _run_command(self, command: List[str], timeout: int = 300) -> tuple[str, str, int]:
        """Run a command and return output, error, and return code"""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Command timed out: {' '.join(command)}")
            return "", "Command timed out", 124
        except Exception as e:
            self.logger.error(f"Command failed: {e}")
            return "", str(e), 1
    
    def sqlmap_scan(self, target: str, data: str = None, 
                   method: str = "GET", cookie: str = None,
                   user_agent: str = None) -> List[WebVulnerability]:
        """SQL injection scanning using SQLMap"""
        self.logger.info(f"SQLMap scanning {target}")
        
        command = [
            "sqlmap", "-u", target, "--batch", "--no-cast",
            "--tamper=space2comment", "--level=5", "--risk=3",
            "--dbs", "--tables", "--columns", "--dump"
        ]
        
        if data:
            command.extend(["-d", data])
        
        if method.upper() == "POST":
            command.append("--data")
        
        if cookie:
            command.extend(["--cookie", cookie])
        
        if user_agent:
            command.extend(["--user-agent", user_agent])
        
        stdout, stderr, rc = self._run_command(command, timeout=600)
        
        vulnerabilities = []
        if rc == 0:
            # Parse SQLMap output for vulnerabilities
            if "is vulnerable" in stdout.lower():
                vuln = WebVulnerability(
                    name="SQL Injection",
                    severity="high",
                    url=target,
                    description="SQL injection vulnerability detected"
                )
                vulnerabilities.append(vuln)
            
            # Extract CVE information
            cve_matches = re.findall(r'CVE-\d{4}-\d+', stdout)
            for cve in cve_matches:
                vuln = WebVulnerability(
                    name=f"SQL Injection - {cve}",
                    severity="high",
                    url=target,
                    description=f"SQL injection vulnerability: {cve}"
                )
                vulnerabilities.append(vuln)
        
        return vulnerabilities
    
    def dirb_scan(self, target: str, wordlist: str = None, 
                 extensions: List[str] = None) -> List[DirectoryResult]:
        """Directory brute force using DIRB"""
        self.logger.info(f"DIRB scanning {target}")
        
        command = ["dirb", target]
        
        if wordlist:
            command.extend(["-w", wordlist])
        
        if extensions:
            ext_str = ",".join(extensions)
            command.extend(["-X", ext_str])
        
        stdout, stderr, rc = self._run_command(command, timeout=600)
        
        directories = []
        if rc == 0:
            for line in stdout.split('\n'):
                if 'CODE:' in line and 'SIZE:' in line:
                    # Parse DIRB output
                    status_match = re.search(r'CODE:(\d+)', line)
                    size_match = re.search(r'SIZE:(\d+)', line)
                    url_match = re.search(r'\+ (http[s]?://[^\s]+)', line)
                    
                    if status_match and size_match and url_match:
                        directory = DirectoryResult(
                            url=url_match.group(1),
                            status_code=int(status_match.group(1)),
                            content_length=int(size_match.group(1))
                        )
                        directories.append(directory)
        
        return directories
    
    def gobuster_scan(self, target: str, wordlist: str = None,
                     scan_type: str = "dir", extensions: List[str] = None) -> List[DirectoryResult]:
        """Directory/file brute force using Gobuster"""
        self.logger.info(f"Gobuster {scan_type} scanning {target}")
        
        if wordlist is None:
            if scan_type == "dir":
                wordlist = "/usr/share/wordlists/dirb/common.txt"
            else:
                wordlist = "/usr/share/wordlists/dirb/big.txt"
        
        command = [
            "gobuster", scan_type, "-u", target, "-w", wordlist,
            "-t", "50", "-q"
        ]
        
        if extensions:
            ext_str = ",".join(extensions)
            command.extend(["-x", ext_str])
        
        stdout, stderr, rc = self._run_command(command, timeout=600)
        
        directories = []
        if rc == 0:
            for line in stdout.split('\n'):
                if 'Status:' in line and 'Size:' in line:
                    # Parse Gobuster output
                    parts = line.split()
                    if len(parts) >= 3:
                        url = parts[0]
                        status_code = int(parts[1].replace('Status:', ''))
                        content_length = int(parts[2].replace('Size:', ''))
                        
                        directory = DirectoryResult(
                            url=url,
                            status_code=status_code,
                            content_length=content_length
                        )
                        directories.append(directory)
        
        return directories
    
    def wfuzz_scan(self, target: str, wordlist: str = None,
                  parameter: str = "FUZZ", method: str = "GET") -> List[DirectoryResult]:
        """Web fuzzing using WFuzz"""
        self.logger.info(f"WFuzz scanning {target}")
        
        if wordlist is None:
            wordlist = "/usr/share/wordlists/dirb/common.txt"
        
        # Replace FUZZ placeholder in target URL
        if "FUZZ" not in target:
            if "?" in target:
                target += f"&{parameter}=FUZZ"
            else:
                target += f"?{parameter}=FUZZ"
        
        command = [
            "wfuzz", "-w", wordlist, "-c", "-z", "list,{method}",
            target
        ]
        
        stdout, stderr, rc = self._run_command(command, timeout=600)
        
        directories = []
        if rc == 0:
            for line in stdout.split('\n'):
                if 'C=' in line and 'L=' in line and 'W=' in line:
                    # Parse WFuzz output
                    parts = line.split()
                    if len(parts) >= 4:
                        url = parts[3]
                        # Extract status code and length
                        status_match = re.search(r'C=(\d+)', line)
                        length_match = re.search(r'L=(\d+)', line)
                        
                        if status_match and length_match:
                            directory = DirectoryResult(
                                url=url,
                                status_code=int(status_match.group(1)),
                                content_length=int(length_match.group(1))
                            )
                            directories.append(directory)
        
        return directories
    
    def nikto_scan(self, target: str, port: int = 80) -> List[WebVulnerability]:
        """Web vulnerability scanning using Nikto"""
        self.logger.info(f"Nikto scanning {target}:{port}")
        
        command = [
            "nikto", "-h", target, "-p", str(port), "-Format", "json"
        ]
        
        stdout, stderr, rc = self._run_command(command, timeout=600)
        
        vulnerabilities = []
        if rc == 0:
            try:
                data = json.loads(stdout)
                if "vulnerabilities" in data:
                    for vuln_data in data["vulnerabilities"]:
                        vuln = WebVulnerability(
                            name=vuln_data.get("id", "Unknown"),
                            severity="medium",
                            url=target,
                            description=vuln_data.get("description", "")
                        )
                        vulnerabilities.append(vuln)
            except json.JSONDecodeError:
                # Fallback to text parsing
                vulnerabilities = self._parse_nikto_text(stdout, target)
        
        return vulnerabilities
    
    def _parse_nikto_text(self, output: str, target: str) -> List[WebVulnerability]:
        """Parse Nikto text output"""
        vulnerabilities = []
        
        for line in output.split('\n'):
            if '+ ' in line and ('OSVDB' in line or 'CVE' in line):
                vuln_info = line.split('+ ')[1].strip()
                
                # Extract CVE if present
                cve = None
                cve_match = re.search(r'CVE-\d{4}-\d+', vuln_info)
                if cve_match:
                    cve = cve_match.group()
                
                vuln = WebVulnerability(
                    name=vuln_info[:100],
                    severity="medium",
                    url=target,
                    cve=cve,
                    description=vuln_info
                )
                vulnerabilities.append(vuln)
        
        return vulnerabilities
    
    def whatweb_scan(self, target: str) -> Dict[str, Any]:
        """Technology detection using WhatWeb"""
        self.logger.info(f"WhatWeb scanning {target}")
        
        command = [
            "whatweb", "-a", "3", "--log-json=-", target
        ]
        
        stdout, stderr, rc = self._run_command(command, timeout=120)
        
        technologies = {}
        if rc == 0:
            try:
                data = json.loads(stdout)
                if "plugins" in data:
                    for plugin in data["plugins"]:
                        technologies[plugin["name"]] = plugin.get("version", "Unknown")
            except json.JSONDecodeError:
                # Fallback to text parsing
                technologies = self._parse_whatweb_text(stdout)
        
        return technologies
    
    def _parse_whatweb_text(self, output: str) -> Dict[str, str]:
        """Parse WhatWeb text output"""
        technologies = {}
        
        for line in output.split('\n'):
            if '[' in line and ']' in line:
                # Extract technology information
                parts = line.split('[')
                if len(parts) >= 2:
                    tech_info = parts[1].split(']')[0]
                    tech_parts = tech_info.split(',')
                    for tech in tech_parts:
                        tech = tech.strip()
                        if tech and tech not in ['200', 'OK']:
                            technologies[tech] = "Unknown"
        
        return technologies
    
    def wapiti_scan(self, target: str) -> List[WebVulnerability]:
        """Web vulnerability scanning using Wapiti"""
        self.logger.info(f"Wapiti scanning {target}")
        
        command = [
            "wapiti", "-u", target, "-f", "json", "-o", "/tmp/wapiti_report"
        ]
        
        stdout, stderr, rc = self._run_command(command, timeout=900)
        
        vulnerabilities = []
        if rc == 0:
            try:
                # Read the generated JSON report
                with open("/tmp/wapiti_report", 'r') as f:
                    data = json.load(f)
                
                if "vulnerabilities" in data:
                    for vuln_data in data["vulnerabilities"]:
                        vuln = WebVulnerability(
                            name=vuln_data.get("name", "Unknown"),
                            severity=vuln_data.get("level", "medium"),
                            url=target,
                            description=vuln_data.get("description", "")
                        )
                        vulnerabilities.append(vuln)
            except (json.JSONDecodeError, FileNotFoundError):
                self.logger.error("Failed to parse Wapiti report")
        
        return vulnerabilities
    
    def comprehensive_web_scan(self, target: str) -> WebScanResult:
        """Perform comprehensive web vulnerability scanning"""
        self.logger.info(f"Comprehensive web scan of {target}")
        
        all_vulnerabilities = []
        all_directories = []
        
        # Nikto scan
        try:
            nikto_vulns = self.nikto_scan(target)
            all_vulnerabilities.extend(nikto_vulns)
        except Exception as e:
            self.logger.error(f"Nikto scan failed: {e}")
        
        # SQLMap scan
        try:
            sqlmap_vulns = self.sqlmap_scan(target)
            all_vulnerabilities.extend(sqlmap_vulns)
        except Exception as e:
            self.logger.error(f"SQLMap scan failed: {e}")
        
        # Wapiti scan
        try:
            wapiti_vulns = self.wapiti_scan(target)
            all_vulnerabilities.extend(wapiti_vulns)
        except Exception as e:
            self.logger.error(f"Wapiti scan failed: {e}")
        
        # Directory enumeration
        try:
            dirb_results = self.dirb_scan(target)
            all_directories.extend(dirb_results)
        except Exception as e:
            self.logger.error(f"DIRB scan failed: {e}")
        
        try:
            gobuster_results = self.gobuster_scan(target)
            all_directories.extend(gobuster_results)
        except Exception as e:
            self.logger.error(f"Gobuster scan failed: {e}")
        
        return WebScanResult(
            target=target,
            vulnerabilities=all_vulnerabilities,
            directories=all_directories,
            scan_type="comprehensive",
            timestamp=time.time()
        )
    
    def __del__(self):
        """Cleanup thread pool"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)


# Global instance
web_tools = WebTools()
