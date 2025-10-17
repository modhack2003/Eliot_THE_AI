"""
Simple MCP client for ELIOT to communicate with Kali MCP server
"""

import requests
import json
import logging
from typing import Optional, Dict, Any

class MCPClient:
    """Simple client to communicate with Kali MCP server"""
    
    def __init__(self, server_url: str = "http://localhost:5000"):
        self.server_url = server_url
        self.logger = logging.getLogger("mcp_client")
    
    def execute_command(self, command: str, timeout: int = 300) -> Dict[str, Any]:
        """Execute a command via MCP server"""
        try:
            payload = {
                "command": command,
                "timeout": timeout
            }
            
            response = requests.post(
                f"{self.server_url}/api/command",
                json=payload,
                timeout=timeout + 10
            )
            
            if response.status_code == 200:
                result = response.json()
                # Handle the MCP server response format
                return {
                    "success": result.get("success", True),
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "return_code": result.get("return_code", 0),
                    "error": "" if result.get("success", True) else "Command failed"
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "stdout": "",
                    "stderr": ""
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": f"Command timed out after {timeout} seconds",
                "stdout": "",
                "stderr": ""
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": ""
            }
    
    def check_health(self) -> bool:
        """Check if MCP server is healthy"""
        try:
            response = requests.get(f"{self.server_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def get_available_tools(self) -> Dict[str, bool]:
        """Get list of available tools"""
        try:
            response = requests.get(f"{self.server_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get("tools_status", {})
        except:
            pass
        return {}
