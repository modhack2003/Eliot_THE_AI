"""
Continuous network scanning for target discovery
"""

import asyncio
import time
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..tools.network_tools import network_tools
from ..persistence.database import get_database, Target, Experience
from ..persistence.logger import get_action_logger


@dataclass
class ScanJob:
    """Represents a scanning job"""
    target: str
    scan_type: str
    priority: int = 1
    scheduled_time: float = 0
    retry_count: int = 0
    max_retries: int = 3


class NetworkScanner:
    """Continuous network scanner for autonomous target discovery"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("network_scanner")
        self.action_logger = get_action_logger()
        self.db = None
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.scan_queue = asyncio.Queue()
        self.running = False
        self.discovered_networks = set()
        self.scan_stats = {
            "total_scans": 0,
            "successful_scans": 0,
            "failed_scans": 0,
            "hosts_discovered": 0,
            "networks_scanned": 0
        }
    
    async def initialize(self):
        """Initialize the scanner"""
        self.db = await get_database()
        self.logger.info("Network scanner initialized")
    
    async def start_continuous_scanning(self):
        """Start continuous network scanning"""
        self.running = True
        self.logger.info("Starting continuous network scanning")
        
        # Start scan worker
        asyncio.create_task(self._scan_worker())
        
        # Start network discovery
        asyncio.create_task(self._network_discovery_loop())
        
        # Start periodic scanning
        asyncio.create_task(self._periodic_scan_loop())
        
        # Start queue processor
        asyncio.create_task(self._process_scan_queue())
    
    async def stop_scanning(self):
        """Stop continuous scanning"""
        self.running = False
        self.logger.info("Stopping continuous network scanning")
    
    async def _network_discovery_loop(self):
        """Continuously discover new networks"""
        while self.running:
            try:
                # Discover networks
                networks = await self._discover_networks()
                
                for network in networks:
                    if network not in self.discovered_networks:
                        self.discovered_networks.add(network)
                        self.logger.info(f"Discovered new network: {network}")
                        
                        # Schedule network scan
                        await self._schedule_network_scan(network)
                
                # Wait before next discovery
                await asyncio.sleep(300)  # 5 minutes
                
            except Exception as e:
                self.logger.error(f"Network discovery error: {e}")
                await asyncio.sleep(60)
    
    async def _discover_networks(self) -> List[str]:
        """Discover available networks"""
        try:
            # Use network_tools to discover networks
            networks = network_tools.discover_networks()
            return networks
        except Exception as e:
            self.logger.error(f"Failed to discover networks: {e}")
            return []
    
    async def _schedule_network_scan(self, network: str):
        """Schedule a network for scanning"""
        scan_job = ScanJob(
            target=network,
            scan_type="network_discovery",
            priority=1
        )
        await self.scan_queue.put(scan_job)
    
    async def _periodic_scan_loop(self):
        """Periodically rescan known targets"""
        while self.running:
            try:
                # Get all known targets
                targets = await self.db.get_all_targets()
                
                for target in targets:
                    # Skip if recently scanned (within last hour)
                    if time.time() - target.last_seen < 3600:
                        continue
                    
                    # Schedule rescan
                    scan_job = ScanJob(
                        target=target.ip,
                        scan_type="rescan",
                        priority=2
                    )
                    await self.scan_queue.put(scan_job)
                
                # Wait before next periodic scan
                await asyncio.sleep(3600)  # 1 hour
                
            except Exception as e:
                self.logger.error(f"Periodic scan error: {e}")
                await asyncio.sleep(300)
    
    async def _process_scan_queue(self):
        """Process the scan queue"""
        while self.running:
            try:
                # Get next scan job
                scan_job = await self.scan_queue.get()
                
                # Execute scan
                await self._execute_scan_job(scan_job)
                
                # Mark task as done
                self.scan_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Scan queue processing error: {e}")
                await asyncio.sleep(5)
    
    async def _execute_scan_job(self, scan_job: ScanJob):
        """Execute a scan job"""
        try:
            self.logger.info(f"Executing scan job: {scan_job.scan_type} on {scan_job.target}")
            
            start_time = time.time()
            
            if scan_job.scan_type == "network_discovery":
                result = await self._scan_network(scan_job.target)
            elif scan_job.scan_type == "rescan":
                result = await self._rescan_target(scan_job.target)
            elif scan_job.scan_type == "port_scan":
                result = await self._port_scan_target(scan_job.target)
            else:
                self.logger.warning(f"Unknown scan type: {scan_job.scan_type}")
                return
            
            duration = time.time() - start_time
            
            # Log the scan
            self.action_logger.log_discovery(
                scan_job.target,
                scan_job.scan_type,
                result
            )
            
            # Update statistics
            self.scan_stats["total_scans"] += 1
            if result.get("success", False):
                self.scan_stats["successful_scans"] += 1
            else:
                self.scan_stats["failed_scans"] += 1
            
            # Store experience
            if self.db:
                experience = Experience(
                    target=scan_job.target,
                    action=f"scan_{scan_job.scan_type}",
                    tool_used="network_tools",
                    success=result.get("success", False),
                    timestamp=time.time(),
                    context={"scan_job": scan_job.__dict__},
                    result=result
                )
                await self.db.store_experience(experience)
            
        except Exception as e:
            self.logger.error(f"Failed to execute scan job: {e}")
            
            # Retry if possible
            if scan_job.retry_count < scan_job.max_retries:
                scan_job.retry_count += 1
                scan_job.scheduled_time = time.time() + (scan_job.retry_count * 60)
                await self.scan_queue.put(scan_job)
    
    async def _scan_network(self, network: str) -> Dict[str, Any]:
        """Scan a network for hosts"""
        try:
            # Use network_tools to scan network
            hosts = network_tools.nmap_host_discovery([network], aggressive=True)
            
            result = {
                "success": True,
                "hosts_found": len(hosts),
                "hosts": [host.__dict__ for host in hosts]
            }
            
            # Store discovered hosts as targets
            for host in hosts:
                target = Target(
                    ip=host.ip,
                    hostname=host.hostname,
                    last_seen=time.time(),
                    priority=1
                )
                await self.db.store_target(target)
                
                # Schedule port scan
                scan_job = ScanJob(
                    target=host.ip,
                    scan_type="port_scan",
                    priority=2
                )
                await self.scan_queue.put(scan_job)
            
            self.scan_stats["hosts_discovered"] += len(hosts)
            self.scan_stats["networks_scanned"] += 1
            
            return result
            
        except Exception as e:
            self.logger.error(f"Network scan failed for {network}: {e}")
            return {
                "success": False,
                "error": str(e),
                "hosts_found": 0
            }
    
    async def _rescan_target(self, ip: str) -> Dict[str, Any]:
        """Rescan a known target"""
        try:
            # Get target from database
            target = await self.db.get_target(ip)
            if not target:
                return {"success": False, "error": "Target not found"}
            
            # Check if target is still alive
            hosts = network_tools.nmap_host_discovery([ip], aggressive=True)
            
            if hosts:
                # Target is alive, update last_seen
                target.last_seen = time.time()
                await self.db.store_target(target)
                
                return {
                    "success": True,
                    "target_alive": True,
                    "last_seen": target.last_seen
                }
            else:
                # Target appears to be down
                return {
                    "success": True,
                    "target_alive": False,
                    "last_seen": target.last_seen
                }
                
        except Exception as e:
            self.logger.error(f"Target rescan failed for {ip}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _port_scan_target(self, ip: str) -> Dict[str, Any]:
        """Perform port scan on target"""
        try:
            # Use network_tools for port scanning
            port_results = network_tools.nmap_port_scan([ip], aggressive=True)
            ports = port_results.get(ip, [])
            
            result = {
                "success": True,
                "ports_found": len(ports),
                "ports": [port.__dict__ for port in ports]
            }
            
            # Update target with port information
            target = await self.db.get_target(ip)
            if target:
                target.services = [port.__dict__ for port in ports]
                target.last_seen = time.time()
                await self.db.store_target(target)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Port scan failed for {ip}: {e}")
            return {
                "success": False,
                "error": str(e),
                "ports_found": 0
            }
    
    async def add_manual_target(self, ip: str, priority: int = 1):
        """Add a manual target for scanning"""
        try:
            # Validate IP address
            ipaddress.ip_address(ip)
            
            # Create target
            target = Target(
                ip=ip,
                priority=priority,
                last_seen=0
            )
            await self.db.store_target(target)
            
            # Schedule immediate scan
            scan_job = ScanJob(
                target=ip,
                scan_type="port_scan",
                priority=priority
            )
            await self.scan_queue.put(scan_job)
            
            self.logger.info(f"Added manual target: {ip}")
            
        except Exception as e:
            self.logger.error(f"Failed to add manual target {ip}: {e}")
    
    async def get_scan_statistics(self) -> Dict[str, Any]:
        """Get scanning statistics"""
        stats = self.scan_stats.copy()
        stats["queue_size"] = self.scan_queue.qsize()
        stats["discovered_networks"] = len(self.discovered_networks)
        stats["running"] = self.running
        
        return stats
    
    async def _scan_worker(self):
        """Background scan worker"""
        while self.running:
            try:
                # Process any pending scans
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.error(f"Scan worker error: {e}")
                await asyncio.sleep(5)


# Global scanner instance
scanner_instance = None


async def get_scanner(config) -> NetworkScanner:
    """Get or create scanner instance"""
    global scanner_instance
    
    if scanner_instance is None:
        scanner_instance = NetworkScanner(config)
        await scanner_instance.initialize()
    
    return scanner_instance
