"""
Password cracking tools wrapper for Kali Linux
"""

import subprocess
import os
import hashlib
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class PasswordResult:
    """Result of password cracking"""
    username: str
    password: str
    hash_type: Optional[str] = None
    success: bool = False
    method: str = "unknown"


@dataclass
class HashInfo:
    """Information about a hash"""
    hash_value: str
    hash_type: str
    username: Optional[str] = None
    salt: Optional[str] = None


class PasswordTools:
    """Wrapper for password cracking tools"""
    
    def __init__(self):
        self.logger = logging.getLogger("password_tools")
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.wordlists = {
            "common": "/usr/share/wordlists/rockyou.txt",
            "fasttrack": "/usr/share/wordlists/fasttrack.txt",
            "big": "/usr/share/wordlists/big.txt",
            "small": "/usr/share/wordlists/small.txt"
        }
    
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
    
    def identify_hash(self, hash_value: str) -> Optional[str]:
        """Identify hash type using hash-identifier"""
        self.logger.info(f"Identifying hash: {hash_value[:20]}...")
        
        # Create temporary file with hash
        hash_file = f"/tmp/hash_{hash_value[:10]}.txt"
        with open(hash_file, 'w') as f:
            f.write(hash_value)
        
        command = ["hash-identifier", hash_file]
        stdout, stderr, rc = self._run_command(command, timeout=30)
        
        # Cleanup
        try:
            os.remove(hash_file)
        except:
            pass
        
        if rc == 0:
            # Parse hash-identifier output
            for line in stdout.split('\n'):
                if 'Possible Hash Type:' in line:
                    hash_type = line.split(':')[1].strip()
                    return hash_type
        
        return None
    
    def john_crack(self, hash_file: str, wordlist: str = None, 
                  hash_type: str = None) -> List[PasswordResult]:
        """Password cracking using John the Ripper"""
        self.logger.info(f"John cracking hash file: {hash_file}")
        
        if wordlist is None:
            wordlist = self.wordlists["common"]
        
        command = ["john", "--wordlist", wordlist]
        
        if hash_type:
            command.extend(["--format", hash_type])
        
        command.append(hash_file)
        
        stdout, stderr, rc = self._run_command(command, timeout=1800)
        
        results = []
        if rc == 0:
            # Get cracked passwords
            show_command = ["john", "--show", hash_file]
            show_stdout, show_stderr, show_rc = self._run_command(show_command, timeout=30)
            
            if show_rc == 0:
                results = self._parse_john_output(show_stdout)
        
        return results
    
    def _parse_john_output(self, output: str) -> List[PasswordResult]:
        """Parse John the Ripper output"""
        results = []
        
        for line in output.split('\n'):
            if ':' in line and line.strip():
                parts = line.split(':')
                if len(parts) >= 2:
                    username = parts[0]
                    password = parts[1]
                    
                    result = PasswordResult(
                        username=username,
                        password=password,
                        success=True,
                        method="john"
                    )
                    results.append(result)
        
        return results
    
    def hashcat_crack(self, hash_file: str, wordlist: str = None,
                     hash_type: int = None, attack_mode: int = 0) -> List[PasswordResult]:
        """Password cracking using Hashcat"""
        self.logger.info(f"Hashcat cracking hash file: {hash_file}")
        
        if wordlist is None:
            wordlist = self.wordlists["common"]
        
        command = ["hashcat", "-a", str(attack_mode)]
        
        if hash_type:
            command.extend(["-m", str(hash_type)])
        
        command.extend(["-o", "/tmp/hashcat_results.txt", hash_file, wordlist])
        
        stdout, stderr, rc = self._run_command(command, timeout=1800)
        
        results = []
        if rc == 0 or rc == 1:  # Hashcat returns 1 when passwords are found
            # Read results file
            try:
                with open("/tmp/hashcat_results.txt", 'r') as f:
                    for line in f:
                        if ':' in line:
                            parts = line.strip().split(':')
                            if len(parts) >= 2:
                                result = PasswordResult(
                                    username=parts[0] if len(parts) > 2 else "unknown",
                                    password=parts[-1],
                                    success=True,
                                    method="hashcat"
                                )
                                results.append(result)
            except FileNotFoundError:
                pass
        
        return results
    
    def hydra_bruteforce(self, target: str, service: str, username_list: List[str],
                        password_list: List[str] = None, port: int = None) -> List[PasswordResult]:
        """Brute force authentication using Hydra"""
        self.logger.info(f"Hydra brute forcing {service} on {target}")
        
        if password_list is None:
            password_list = ["admin", "password", "123456", "root", "toor", "administrator"]
        
        # Create temporary files for usernames and passwords
        user_file = f"/tmp/users_{target}.txt"
        pass_file = f"/tmp/passwords_{target}.txt"
        
        with open(user_file, 'w') as f:
            f.write('\n'.join(username_list))
        
        with open(pass_file, 'w') as f:
            f.write('\n'.join(password_list))
        
        command = [
            "hydra", "-L", user_file, "-P", pass_file,
            "-t", "4", "-vV", service
        ]
        
        if port:
            command.extend(["-s", str(port)])
        
        command.append(target)
        
        stdout, stderr, rc = self._run_command(command, timeout=600)
        
        results = []
        if rc == 0:
            results = self._parse_hydra_output(stdout)
        
        # Cleanup
        try:
            os.remove(user_file)
            os.remove(pass_file)
        except:
            pass
        
        return results
    
    def _parse_hydra_output(self, output: str) -> List[PasswordResult]:
        """Parse Hydra output"""
        results = []
        
        for line in output.split('\n'):
            if 'login:' in line and 'password:' in line:
                # Extract credentials
                parts = line.split()
                username = None
                password = None
                
                for i, part in enumerate(parts):
                    if part == 'login:':
                        username = parts[i + 1]
                    elif part == 'password:':
                        password = parts[i + 1]
                
                if username and password:
                    result = PasswordResult(
                        username=username,
                        password=password,
                        success=True,
                        method="hydra"
                    )
                    results.append(result)
        
        return results
    
    def medusa_bruteforce(self, target: str, service: str, username_list: List[str],
                         password_list: List[str] = None, port: int = None) -> List[PasswordResult]:
        """Brute force authentication using Medusa"""
        self.logger.info(f"Medusa brute forcing {service} on {target}")
        
        if password_list is None:
            password_list = ["admin", "password", "123456", "root", "toor"]
        
        # Create temporary files
        user_file = f"/tmp/medusa_users_{target}.txt"
        pass_file = f"/tmp/medusa_passwords_{target}.txt"
        
        with open(user_file, 'w') as f:
            f.write('\n'.join(username_list))
        
        with open(pass_file, 'w') as f:
            f.write('\n'.join(password_list))
        
        command = [
            "medusa", "-h", target, "-u", user_file, "-p", pass_file,
            "-M", service, "-t", "4", "-v", "4"
        ]
        
        if port:
            command.extend(["-n", str(port)])
        
        stdout, stderr, rc = self._run_command(command, timeout=600)
        
        results = []
        if rc == 0:
            results = self._parse_medusa_output(stdout)
        
        # Cleanup
        try:
            os.remove(user_file)
            os.remove(pass_file)
        except:
            pass
        
        return results
    
    def _parse_medusa_output(self, output: str) -> List[PasswordResult]:
        """Parse Medusa output"""
        results = []
        
        for line in output.split('\n'):
            if 'SUCCESS' in line:
                # Extract credentials from success line
                parts = line.split()
                username = None
                password = None
                
                for i, part in enumerate(parts):
                    if part.startswith('[') and part.endswith(']'):
                        username = part.strip('[]')
                    elif part == 'SUCCESS':
                        if i + 1 < len(parts):
                            password = parts[i + 1]
                
                if username and password:
                    result = PasswordResult(
                        username=username,
                        password=password,
                        success=True,
                        method="medusa"
                    )
                    results.append(result)
        
        return results
    
    def generate_wordlist(self, target_info: Dict[str, Any], 
                         output_file: str = "/tmp/custom_wordlist.txt") -> str:
        """Generate custom wordlist based on target information"""
        self.logger.info("Generating custom wordlist")
        
        words = set()
        
        # Add common passwords
        common_passwords = [
            "admin", "password", "123456", "root", "toor", "administrator",
            "guest", "user", "test", "demo", "default", "changeme",
            "password123", "admin123", "root123", "12345", "qwerty"
        ]
        words.update(common_passwords)
        
        # Add target-specific words
        if "company_name" in target_info:
            company = target_info["company_name"].lower()
            words.add(company)
            words.add(f"{company}123")
            words.add(f"{company}admin")
        
        if "domain" in target_info:
            domain = target_info["domain"].lower()
            words.add(domain)
            words.add(f"{domain}123")
        
        if "os" in target_info:
            os_name = target_info["os"].lower()
            words.add(os_name)
            words.add(f"{os_name}123")
        
        # Add years
        import datetime
        current_year = datetime.datetime.now().year
        for year in range(current_year - 10, current_year + 1):
            words.add(str(year))
        
        # Write wordlist to file
        with open(output_file, 'w') as f:
            for word in sorted(words):
                f.write(f"{word}\n")
        
        return output_file
    
    def crack_common_hashes(self, hash_file: str) -> List[PasswordResult]:
        """Crack common hash types using multiple tools"""
        self.logger.info(f"Cracking common hashes from: {hash_file}")
        
        all_results = []
        
        # Try with John
        try:
            john_results = self.john_crack(hash_file)
            all_results.extend(john_results)
        except Exception as e:
            self.logger.error(f"John cracking failed: {e}")
        
        # Try with Hashcat (if John didn't find anything)
        if not all_results:
            try:
                hashcat_results = self.hashcat_crack(hash_file)
                all_results.extend(hashcat_results)
            except Exception as e:
                self.logger.error(f"Hashcat cracking failed: {e}")
        
        return all_results
    
    def brute_force_service(self, target: str, service: str, port: int = None) -> List[PasswordResult]:
        """Brute force common services"""
        self.logger.info(f"Brute forcing {service} on {target}")
        
        # Common usernames for different services
        service_users = {
            "ssh": ["root", "admin", "ubuntu", "user", "test"],
            "ftp": ["anonymous", "ftp", "admin", "root", "user"],
            "telnet": ["root", "admin", "user", "guest"],
            "http-get": ["admin", "administrator", "root", "user"],
            "http-post-form": ["admin", "administrator", "root", "user"],
            "mysql": ["root", "admin", "mysql", "user"],
            "postgres": ["postgres", "admin", "root", "user"],
            "smb": ["administrator", "admin", "guest", "user"]
        }
        
        usernames = service_users.get(service, ["admin", "root", "user", "guest"])
        
        # Try Hydra first
        try:
            hydra_results = self.hydra_bruteforce(target, service, usernames, port=port)
            if hydra_results:
                return hydra_results
        except Exception as e:
            self.logger.error(f"Hydra brute force failed: {e}")
        
        # Try Medusa as fallback
        try:
            medusa_results = self.medusa_bruteforce(target, service, usernames, port=port)
            return medusa_results
        except Exception as e:
            self.logger.error(f"Medusa brute force failed: {e}")
        
        return []
    
    def __del__(self):
        """Cleanup thread pool"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)


# Global instance
password_tools = PasswordTools()
