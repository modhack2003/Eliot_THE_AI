"""
Network discovery and scanning tools wrapper for Kali Linux
"""

import subprocess
import json
import re
import ipaddress
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class Host:
    """Represents a discovered host"""
    ip: str
    mac: Optional[str] = None
    hostname: Optional[str] = None
    vendor: Optional[str] = None
    status: str = "unknown"


@dataclass
class Port:
    """Represents an open port"""
    port: int
    protocol: str
    state: str
    service: Optional[str] = None
    version: Optional[str] = None
    banner: Optional[str] = None


@dataclass
class ScanResult:
    """Result of a network scan"""
    target: str
    hosts: List[Host]
    ports: List[Port]
    scan_type: str
    timestamp: float


class NetworkTools:
    """Wrapper for network discovery and scanning tools"""
    
    def __init__(self):
        self.logger = logging.getLogger("network_tools")
        self.executor = ThreadPoolExecutor(max_workers=10)
    
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
    
    def discover_networks(self) -> List[str]:
        """Discover available networks using netdiscover"""
        self.logger.info("Discovering available networks...")
        
        # Get network interfaces
        stdout, stderr, rc = self._run_command(["ip", "route", "show"])
        networks = []
        
        if rc == 0:
            for line in stdout.split('\n'):
                if 'default via' in line:
                    # Extract network from default route
                    parts = line.split()
                    if len(parts) >= 3:
                        gateway = parts[2]
                        # Try to determine network from gateway
                        try:
                            gateway_ip = ipaddress.ip_address(gateway)
                            # Assume /24 network
                            network = ipaddress.ip_network(f"{gateway_ip}/24", strict=False)
                            networks.append(str(network))
                        except:
                            continue
        
        # Fallback: scan common private networks
        if not networks:
            networks = [
                "192.168.1.0/24",
                "192.168.0.0/24", 
                "10.0.0.0/8",
                "172.16.0.0/12"
            ]
        
        return networks
    
    def nmap_host_discovery(self, targets: List[str], aggressive: bool = True) -> List[Host]:
        """Discover live hosts using nmap"""
        self.logger.info(f"Discovering hosts in {targets}")
        hosts = []
        
        for target in targets:
            if aggressive:
                # Aggressive host discovery
                command = [
                    "nmap", "-sn", "--send-ip", "-T4",
                    "--min-hostgroup", "256", "--min-parallelism", "256",
                    target
                ]
            else:
                # Stealth host discovery
                command = [
                    "nmap", "-sn", "-PS", "-PA", "-PU", "-PY",
                    target
                ]
            
            stdout, stderr, rc = self._run_command(command, timeout=600)
            
            if rc == 0:
                # Parse nmap output
                for line in stdout.split('\n'):
                    if 'Nmap scan report for' in line:
                        # Extract IP and hostname
                        parts = line.split()
                        if len(parts) >= 5:
                            ip = parts[-1].strip('()')
                            hostname = parts[4].strip('()') if '(' in line else None
                            
                            host = Host(ip=ip, hostname=hostname, status="up")
                            hosts.append(host)
            
            # Also try ARP scan for local networks
            if target.endswith('/24'):
                arp_hosts = self._arp_scan(target)
                hosts.extend(arp_hosts)
        
        return hosts
    
    def _arp_scan(self, network: str) -> List[Host]:
        """ARP scan for local network discovery"""
        self.logger.info(f"ARP scanning {network}")
        hosts = []
        
        command = ["arp-scan", "--local", network]
        stdout, stderr, rc = self._run_command(command, timeout=300)
        
        if rc == 0:
            for line in stdout.split('\n'):
                parts = line.split('\t')
                if len(parts) >= 3:
                    ip = parts[0].strip()
                    mac = parts[1].strip()
                    vendor = parts[2].strip()
                    
                    # Validate IP
                    try:
                        ipaddress.ip_address(ip)
                        host = Host(ip=ip, mac=mac, vendor=vendor, status="up")
                        hosts.append(host)
                    except:
                        continue
        
        return hosts
    
    def nmap_port_scan(self, targets: List[str], ports: Optional[str] = None, 
                      aggressive: bool = True) -> Dict[str, List[Port]]:
        """Perform port scanning using nmap"""
        self.logger.info(f"Port scanning {targets}")
        results = {}
        
        for target in targets:
            if ports is None:
                ports = "1-65535" if aggressive else "1-1000"
            
            if aggressive:
                command = [
                    "nmap", "-sS", "-sV", "-sC", "-O", "-A", "--script=vuln",
                    "-p", ports, "-T4", "--min-hostgroup", "256",
                    "--min-parallelism", "256", target
                ]
            else:
                command = [
                    "nmap", "-sS", "-sV", "-sC", "-p", ports, "-T2", target
                ]
            
            stdout, stderr, rc = self._run_command(command, timeout=1800)
            ports_list = []
            
            if rc == 0:
                ports_list = self._parse_nmap_ports(stdout)
            
            results[target] = ports_list
        
        return results
    
    def _parse_nmap_ports(self, output: str) -> List[Port]:
        """Parse nmap port scan output"""
        ports = []
        current_port = None
        
        for line in output.split('\n'):
            line = line.strip()
            
            # Port line: PORT STATE SERVICE VERSION
            if re.match(r'^\d+/(tcp|udp)\s+', line):
                parts = line.split()
                if len(parts) >= 3:
                    port_proto = parts[0].split('/')
                    port_num = int(port_proto[0])
                    protocol = port_proto[1]
                    state = parts[1]
                    service = parts[2] if parts[2] != 'unknown' else None
                    
                    # Look for version info
                    version = None
                    if len(parts) > 3:
                        version_parts = []
                        for part in parts[3:]:
                            if part.startswith('('):
                                break
                            version_parts.append(part)
                        if version_parts:
                            version = ' '.join(version_parts)
                    
                    port = Port(
                        port=port_num,
                        protocol=protocol,
                        state=state,
                        service=service,
                        version=version
                    )
                    ports.append(port)
                    current_port = port
            
            # Banner/version info
            elif current_port and line.startswith('|'):
                if not current_port.banner:
                    current_port.banner = line[1:].strip()
                else:
                    current_port.banner += f"\n{line[1:].strip()}"
        
        return ports
    
    def nmap_script_scan(self, target: str, script: str) -> Dict[str, Any]:
        """Run specific nmap scripts"""
        self.logger.info(f"Running nmap script {script} on {target}")
        
        command = [
            "nmap", "--script", script, "-p-", target
        ]
        
        stdout, stderr, rc = self._run_command(command, timeout=600)
        
        if rc == 0:
            return {
                "success": True,
                "output": stdout,
                "error": stderr
            }
        else:
            return {
                "success": False,
                "output": stdout,
                "error": stderr
            }
    
    def masscan_scan(self, targets: List[str], ports: str = "1-65535", 
                    rate: int = 1000) -> Dict[str, List[Port]]:
        """Fast port scanning using masscan"""
        self.logger.info(f"Masscan scanning {targets}")
        results = {}
        
        for target in targets:
            command = [
                "masscan", "-p", ports, "--rate", str(rate),
                "--open", "-oG", "-", target
            ]
            
            stdout, stderr, rc = self._run_command(command, timeout=600)
            
            if rc == 0:
                # Parse masscan output (grepable format)
                ports_list = []
                for line in stdout.split('\n'):
                    if 'open' in line and 'Ports:' in line:
                        # Extract port info
                        port_match = re.search(r'(\d+)/(\w+)/open', line)
                        if port_match:
                            port_num = int(port_match.group(1))
                            protocol = port_match.group(2)
                            
                            port = Port(
                                port=port_num,
                                protocol=protocol,
                                state="open",
                                service="unknown"
                            )
                            ports_list.append(port)
                
                results[target] = ports_list
        
        return results
    
    def zmap_scan(self, target: str, port: int) -> List[str]:
        """Fast single port scanning using zmap"""
        self.logger.info(f"Zmap scanning port {port} on {target}")
        
        command = [
            "zmap", "-p", str(port), "-B", "10M", target
        ]
        
        stdout, stderr, rc = self._run_command(command, timeout=300)
        hosts = []
        
        if rc == 0:
            for line in stdout.split('\n'):
                ip = line.strip()
                if ip:
                    hosts.append(ip)
        
        return hosts
    
    def comprehensive_scan(self, targets: List[str]) -> List[ScanResult]:
        """Perform comprehensive network scanning"""
        self.logger.info(f"Starting comprehensive scan of {targets}")
        results = []
        
        # Step 1: Host discovery
        hosts = self.nmap_host_discovery(targets, aggressive=True)
        host_ips = [host.ip for host in hosts]
        
        if not host_ips:
            self.logger.warning("No hosts discovered")
            return results
        
        # Step 2: Fast port scan with masscan
        fast_ports = self.masscan_scan(host_ips, ports="1-1000", rate=1000)
        
        # Step 3: Detailed nmap scan on discovered ports
        for target, ports in fast_ports.items():
            if ports:
                # Create port string for nmap
                port_string = ",".join([str(port.port) for port in ports])
                
                # Detailed nmap scan
                detailed_ports = self.nmap_port_scan([target], ports=port_string, aggressive=True)
                
                result = ScanResult(
                    target=target,
                    hosts=[h for h in hosts if h.ip == target],
                    ports=detailed_ports.get(target, []),
                    scan_type="comprehensive",
                    timestamp=time.time()
                )
                results.append(result)
        
        return results
    
    def get_network_info(self, target: str) -> Dict[str, Any]:
        """Get detailed network information for a target"""
        info = {
            "target": target,
            "traceroute": None,
            "whois": None,
            "dns": None
        }
        
        # Traceroute
        stdout, stderr, rc = self._run_command(["traceroute", target], timeout=120)
        if rc == 0:
            info["traceroute"] = stdout
        
        # WHOIS
        stdout, stderr, rc = self._run_command(["whois", target], timeout=60)
        if rc == 0:
            info["whois"] = stdout
        
        # DNS lookup
        stdout, stderr, rc = self._run_command(["nslookup", target], timeout=30)
        if rc == 0:
            info["dns"] = stdout
        
        return info
    
    def __del__(self):
        """Cleanup thread pool"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)


# Global instance
network_tools = NetworkTools()
