"""
Vulnerability scanning tools wrapper for Kali Linux
"""

import subprocess
import json
import xml.etree.ElementTree as ET
import re
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class Vulnerability:
    """Represents a discovered vulnerability"""
    name: str
    severity: str
    cvss_score: Optional[float] = None
    cve: Optional[str] = None
    description: Optional[str] = None
    solution: Optional[str] = None
    references: List[str] = None
    
    def __post_init__(self):
        if self.references is None:
            self.references = []


@dataclass
class VulnScanResult:
    """Result of vulnerability scanning"""
    target: str
    vulnerabilities: List[Vulnerability]
    scan_type: str
    timestamp: float


class VulnScanner:
    """Wrapper for vulnerability scanning tools"""
    
    def __init__(self):
        self.logger = logging.getLogger("vuln_scanner")
        self.executor = ThreadPoolExecutor(max_workers=5)
    
    def _run_command(self, command: List[str], timeout: int = 1800) -> tuple[str, str, int]:
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
    
    def nmap_vuln_scan(self, target: str, ports: Optional[str] = None) -> VulnScanResult:
        """Perform vulnerability scanning using nmap NSE scripts"""
        self.logger.info(f"Nmap vulnerability scanning {target}")
        
        if ports is None:
            ports = "1-65535"
        
        command = [
            "nmap", "--script", "vuln", "-sV", "-p", ports, target
        ]
        
        stdout, stderr, rc = self._run_command(command, timeout=1800)
        vulnerabilities = []
        
        if rc == 0:
            vulnerabilities = self._parse_nmap_vuln_output(stdout)
        
        return VulnScanResult(
            target=target,
            vulnerabilities=vulnerabilities,
            scan_type="nmap_vuln",
            timestamp=time.time()
        )
    
    def _parse_nmap_vuln_output(self, output: str) -> List[Vulnerability]:
        """Parse nmap vulnerability script output"""
        vulnerabilities = []
        current_vuln = None
        
        for line in output.split('\n'):
            line = line.strip()
            
            # Vulnerability header
            if '|' in line and ('VULNERABLE' in line or 'SAFE' in line):
                # Extract vulnerability name
                parts = line.split('|')
                if len(parts) >= 2:
                    vuln_name = parts[1].strip()
                    status = parts[0].strip()
                    
                    if 'VULNERABLE' in status:
                        current_vuln = Vulnerability(
                            name=vuln_name,
                            severity="unknown"
                        )
                        vulnerabilities.append(current_vuln)
            
            # CVE information
            elif current_vuln and 'CVE-' in line:
                cve_match = re.search(r'CVE-\d{4}-\d+', line)
                if cve_match:
                    current_vuln.cve = cve_match.group()
            
            # CVSS score
            elif current_vuln and 'CVSS' in line:
                cvss_match = re.search(r'CVSS:\s*(\d+\.?\d*)', line)
                if cvss_match:
                    try:
                        current_vuln.cvss_score = float(cvss_match.group(1))
                    except:
                        pass
            
            # Description
            elif current_vuln and line.startswith('|') and 'State:' not in line:
                desc = line[1:].strip()
                if desc and not desc.startswith('http'):
                    if not current_vuln.description:
                        current_vuln.description = desc
                    else:
                        current_vuln.description += f" {desc}"
            
            # References
            elif current_vuln and 'http' in line:
                ref_match = re.search(r'http[s]?://[^\s]+', line)
                if ref_match:
                    current_vuln.references.append(ref_match.group())
        
        return vulnerabilities
    
    def nikto_scan(self, target: str, port: int = 80) -> VulnScanResult:
        """Web vulnerability scanning using Nikto"""
        self.logger.info(f"Nikto scanning {target}:{port}")
        
        command = [
            "nikto", "-h", target, "-p", str(port), "-Format", "json"
        ]
        
        stdout, stderr, rc = self._run_command(command, timeout=600)
        vulnerabilities = []
        
        if rc == 0:
            try:
                # Parse JSON output
                data = json.loads(stdout)
                vulnerabilities = self._parse_nikto_json(data)
            except json.JSONDecodeError:
                # Fallback to text parsing
                vulnerabilities = self._parse_nikto_text(stdout)
        
        return VulnScanResult(
            target=target,
            vulnerabilities=vulnerabilities,
            scan_type="nikto",
            timestamp=time.time()
        )
    
    def _parse_nikto_json(self, data: Dict[str, Any]) -> List[Vulnerability]:
        """Parse Nikto JSON output"""
        vulnerabilities = []
        
        if "vulnerabilities" in data:
            for vuln_data in data["vulnerabilities"]:
                vuln = Vulnerability(
                    name=vuln_data.get("id", "Unknown"),
                    severity="medium",  # Nikto doesn't provide severity
                    description=vuln_data.get("description", ""),
                    references=vuln_data.get("references", [])
                )
                vulnerabilities.append(vuln)
        
        return vulnerabilities
    
    def _parse_nikto_text(self, output: str) -> List[Vulnerability]:
        """Parse Nikto text output"""
        vulnerabilities = []
        
        for line in output.split('\n'):
            if '+ ' in line and ('OSVDB' in line or 'CVE' in line):
                # Extract vulnerability info
                parts = line.split('+ ')
                if len(parts) >= 2:
                    vuln_info = parts[1].strip()
                    
                    # Extract CVE if present
                    cve = None
                    cve_match = re.search(r'CVE-\d{4}-\d+', vuln_info)
                    if cve_match:
                        cve = cve_match.group()
                    
                    vuln = Vulnerability(
                        name=vuln_info[:100],  # Limit name length
                        severity="medium",
                        cve=cve,
                        description=vuln_info
                    )
                    vulnerabilities.append(vuln)
        
        return vulnerabilities
    
    def dirb_scan(self, target: str, wordlist: str = None) -> Dict[str, Any]:
        """Directory brute force scanning using DIRB"""
        self.logger.info(f"DIRB scanning {target}")
        
        command = ["dirb", target]
        if wordlist:
            command.extend(["-w", wordlist])
        
        stdout, stderr, rc = self._run_command(command, timeout=600)
        
        directories = []
        files = []
        
        if rc == 0:
            for line in stdout.split('\n'):
                if 'CODE:' in line and 'SIZE:' in line:
                    # Extract directory/file info
                    if 'DIR' in line:
                        dir_match = re.search(r'\+ (http[s]?://[^\s]+)', line)
                        if dir_match:
                            directories.append(dir_match.group(1))
                    else:
                        file_match = re.search(r'\+ (http[s]?://[^\s]+)', line)
                        if file_match:
                            files.append(file_match.group(1))
        
        return {
            "directories": directories,
            "files": files,
            "success": True
        }
    
    def gobuster_scan(self, target: str, wordlist: str = None, 
                     scan_type: str = "dir") -> Dict[str, Any]:
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
        
        stdout, stderr, rc = self._run_command(command, timeout=600)
        
        results = []
        if rc == 0:
            for line in stdout.split('\n'):
                if 'Status:' in line and 'Size:' in line:
                    # Parse result line
                    parts = line.split()
                    if len(parts) >= 3:
                        path = parts[0]
                        status = parts[1].replace('Status:', '')
                        size = parts[2].replace('Size:', '')
                        
                        results.append({
                            "path": path,
                            "status": status,
                            "size": size
                        })
        
        return {
            "results": results,
            "success": rc == 0
        }
    
    def sqlmap_scan(self, target: str, data: str = None, 
                   method: str = "GET") -> Dict[str, Any]:
        """SQL injection scanning using SQLMap"""
        self.logger.info(f"SQLMap scanning {target}")
        
        command = [
            "sqlmap", "-u", target, "--batch", "--no-cast",
            "--tamper=space2comment", "--level=5", "--risk=3"
        ]
        
        if data:
            command.extend(["-d", data])
        
        if method.upper() == "POST":
            command.append("--data")
        
        stdout, stderr, rc = self._run_command(command, timeout=1200)
        
        vulnerabilities = []
        if rc == 0:
            # Parse SQLMap output for vulnerabilities
            for line in stdout.split('\n'):
                if 'is vulnerable' in line.lower():
                    vuln = Vulnerability(
                        name="SQL Injection",
                        severity="high",
                        description=line.strip()
                    )
                    vulnerabilities.append(vuln)
                elif 'CVE-' in line:
                    cve_match = re.search(r'CVE-\d{4}-\d+', line)
                    if cve_match:
                        vuln = Vulnerability(
                            name="SQL Injection",
                            severity="high",
                            cve=cve_match.group(),
                            description=line.strip()
                        )
                        vulnerabilities.append(vuln)
        
        return {
            "vulnerabilities": vulnerabilities,
            "success": len(vulnerabilities) > 0,
            "output": stdout
        }
    
    def openvas_scan(self, target: str, config_id: str = None) -> VulnScanResult:
        """Vulnerability scanning using OpenVAS (if available)"""
        self.logger.info(f"OpenVAS scanning {target}")
        
        # Note: OpenVAS requires specific setup and authentication
        # This is a basic implementation that would need to be adapted
        # based on your OpenVAS setup
        
        command = [
            "omp", "-u", "admin", "-w", "admin", "--xml", 
            f"<create_task><name>Scan_{target}</name><target><hosts>{target}</hosts></target></create_task>"
        ]
        
        stdout, stderr, rc = self._run_command(command, timeout=1800)
        
        vulnerabilities = []
        if rc == 0:
            # Parse OpenVAS XML output
            try:
                root = ET.fromstring(stdout)
                vulnerabilities = self._parse_openvas_xml(root)
            except ET.ParseError:
                self.logger.error("Failed to parse OpenVAS XML output")
        
        return VulnScanResult(
            target=target,
            vulnerabilities=vulnerabilities,
            scan_type="openvas",
            timestamp=time.time()
        )
    
    def _parse_openvas_xml(self, root: ET.Element) -> List[Vulnerability]:
        """Parse OpenVAS XML output"""
        vulnerabilities = []
        
        for result in root.findall(".//result"):
            name = result.find("name")
            severity = result.find("severity")
            description = result.find("description")
            
            if name is not None:
                vuln = Vulnerability(
                    name=name.text or "Unknown",
                    severity=severity.text if severity is not None else "unknown",
                    description=description.text if description is not None else ""
                )
                vulnerabilities.append(vuln)
        
        return vulnerabilities
    
    def comprehensive_vuln_scan(self, target: str, ports: List[int] = None) -> VulnScanResult:
        """Perform comprehensive vulnerability scanning"""
        self.logger.info(f"Comprehensive vulnerability scan of {target}")
        
        if ports is None:
            ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 993, 995, 1433, 3306, 3389, 5432, 5900]
        
        all_vulnerabilities = []
        
        # Nmap vulnerability scan
        try:
            nmap_result = self.nmap_vuln_scan(target)
            all_vulnerabilities.extend(nmap_result.vulnerabilities)
        except Exception as e:
            self.logger.error(f"Nmap vuln scan failed: {e}")
        
        # Web vulnerability scans for HTTP/HTTPS ports
        if 80 in ports:
            try:
                nikto_result = self.nikto_scan(target, 80)
                all_vulnerabilities.extend(nikto_result.vulnerabilities)
            except Exception as e:
                self.logger.error(f"Nikto scan failed: {e}")
        
        if 443 in ports:
            try:
                nikto_result = self.nikto_scan(target, 443)
                all_vulnerabilities.extend(nikto_result.vulnerabilities)
            except Exception as e:
                self.logger.error(f"Nikto HTTPS scan failed: {e}")
        
        # Directory enumeration for web services
        if 80 in ports or 443 in ports:
            try:
                dirb_result = self.dirb_scan(f"http://{target}")
                # Convert directory findings to vulnerabilities
                for directory in dirb_result.get("directories", []):
                    vuln = Vulnerability(
                        name=f"Directory found: {directory}",
                        severity="info",
                        description=f"Directory enumeration discovered: {directory}"
                    )
                    all_vulnerabilities.append(vuln)
            except Exception as e:
                self.logger.error(f"Directory scan failed: {e}")
        
        return VulnScanResult(
            target=target,
            vulnerabilities=all_vulnerabilities,
            scan_type="comprehensive",
            timestamp=time.time()
        )
    
    def __del__(self):
        """Cleanup thread pool"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)


# Global instance
vuln_scanner = VulnScanner()
