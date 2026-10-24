"""
Comprehensive logging system for the autonomous AI pentesting agent
"""

import logging
import logging.handlers
import os
import time
import json
from typing import Dict, Any, Optional
from datetime import datetime
import threading


class PentestingFormatter(logging.Formatter):
    """Custom formatter for pentesting logs"""
    
    def format(self, record):
        # Create base log entry
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'target'):
            log_entry['target'] = record.target
        if hasattr(record, 'action'):
            log_entry['action'] = record.action
        if hasattr(record, 'success'):
            log_entry['success'] = record.success
        if hasattr(record, 'session_id'):
            log_entry['session_id'] = record.session_id
        if hasattr(record, 'exploit_name'):
            log_entry['exploit_name'] = record.exploit_name
        if hasattr(record, 'tool_used'):
            log_entry['tool_used'] = record.tool_used
        if hasattr(record, 'duration'):
            log_entry['duration'] = record.duration
        if hasattr(record, 'error_code'):
            log_entry['error_code'] = record.error_code
        
        return json.dumps(log_entry)


class ActionLogger:
    """Specialized logger for pentesting actions"""
    
    def __init__(self, logger_name: str = "pentesting_actions"):
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)
        
        # Don't propagate to parent loggers
        self.logger.propagate = False
    
    def log_discovery(self, target: str, action: str, result: Dict[str, Any]):
        """Log network discovery actions"""
        extra = {
            'target': target,
            'action': f"discovery_{action}",
            'success': result.get('success', False),
            'tool_used': result.get('tool', 'unknown')
        }
        self.logger.info(f"Discovery {action} on {target}", extra=extra)
    
    def log_scan(self, target: str, scan_type: str, vulnerabilities: int, 
                ports_found: int, duration: float):
        """Log vulnerability scanning"""
        extra = {
            'target': target,
            'action': f"scan_{scan_type}",
            'success': vulnerabilities > 0 or ports_found > 0,
            'tool_used': scan_type,
            'duration': duration
        }
        self.logger.info(
            f"Scan {scan_type} on {target}: {vulnerabilities} vulns, {ports_found} ports",
            extra=extra
        )
    
    def log_exploit(self, target: str, exploit_name: str, success: bool, 
                   session_id: str = None, duration: float = None, error: str = None):
        """Log exploitation attempts"""
        extra = {
            'target': target,
            'action': 'exploit',
            'success': success,
            'exploit_name': exploit_name,
            'session_id': session_id,
            'tool_used': 'metasploit',
            'duration': duration
        }
        
        if error:
            extra['error_code'] = error
        
        status = "SUCCESS" if success else "FAILED"
        message = f"Exploit {exploit_name} on {target}: {status}"
        if session_id:
            message += f" (Session: {session_id})"
        if error:
            message += f" - Error: {error}"
        
        self.logger.info(message, extra=extra)
    
    def log_bruteforce(self, target: str, service: str, success: bool, 
                      credentials: str = None, duration: float = None):
        """Log brute force attempts"""
        extra = {
            'target': target,
            'action': 'bruteforce',
            'success': success,
            'tool_used': service,
            'duration': duration
        }
        
        message = f"Brute force {service} on {target}: {'SUCCESS' if success else 'FAILED'}"
        if credentials:
            message += f" - Credentials: {credentials}"
        
        self.logger.info(message, extra=extra)
    
    def log_session(self, session_id: str, target: str, action: str, 
                   command: str = None, success: bool = True):
        """Log session activities"""
        extra = {
            'target': target,
            'action': f"session_{action}",
            'success': success,
            'session_id': session_id,
            'tool_used': 'metasploit'
        }
        
        message = f"Session {session_id} ({target}): {action}"
        if command:
            message += f" - Command: {command}"
        
        self.logger.info(message, extra=extra)
    
    def log_privilege_escalation(self, session_id: str, target: str, success: bool, 
                               method: str = None, duration: float = None):
        """Log privilege escalation attempts"""
        extra = {
            'target': target,
            'action': 'privilege_escalation',
            'success': success,
            'session_id': session_id,
            'tool_used': method or 'unknown',
            'duration': duration
        }
        
        status = "SUCCESS" if success else "FAILED"
        message = f"Privilege escalation on {target} (Session: {session_id}): {status}"
        if method:
            message += f" - Method: {method}"
        
        self.logger.info(message, extra=extra)
    
    def log_persistence(self, session_id: str, target: str, success: bool, 
                       method: str = None, duration: float = None):
        """Log persistence establishment"""
        extra = {
            'target': target,
            'action': 'persistence',
            'success': success,
            'session_id': session_id,
            'tool_used': method or 'unknown',
            'duration': duration
        }
        
        status = "SUCCESS" if success else "FAILED"
        message = f"Persistence on {target} (Session: {session_id}): {status}"
        if method:
            message += f" - Method: {method}"
        
        self.logger.info(message, extra=extra)
    
    def log_research(self, query: str, source: str, results_count: int, 
                    duration: float = None):
        """Log research activities"""
        extra = {
            'action': 'research',
            'success': results_count > 0,
            'tool_used': source,
            'duration': duration
        }
        
        message = f"Research '{query}' from {source}: {results_count} results"
        self.logger.info(message, extra=extra)
    
    def log_learning(self, action: str, model: str, success: bool, 
                    accuracy: float = None, duration: float = None):
        """Log learning activities"""
        extra = {
            'action': f"learning_{action}",
            'success': success,
            'tool_used': model,
            'duration': duration
        }
        
        message = f"Learning {action} with {model}: {'SUCCESS' if success else 'FAILED'}"
        if accuracy is not None:
            message += f" - Accuracy: {accuracy:.2f}"
        
        self.logger.info(message, extra=extra)


class LoggerManager:
    """Manages all logging for the autonomous agent"""
    
    def __init__(self, config):
        self.config = config
        self.loggers = {}
        self.lock = threading.Lock()
        
        # Create logs directory
        os.makedirs("logs", exist_ok=True)
        
        # Initialize loggers
        self._setup_main_logger()
        self._setup_action_logger()
        self._setup_tool_loggers()
        self._setup_learning_logger()
    
    def _setup_main_logger(self):
        """Setup main agent logger"""
        logger = logging.getLogger("ai_pentesting_agent")
        logger.setLevel(getattr(logging, self.config.logging.level))
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            self.config.logging.file,
            maxBytes=self._parse_size(self.config.logging.max_size),
            backupCount=self.config.logging.backup_count
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = PentestingFormatter()
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        self.loggers['main'] = logger
    
    def _setup_action_logger(self):
        """Setup action logger"""
        logger = logging.getLogger("pentesting_actions")
        logger.setLevel(logging.INFO)
        
        # Separate file for actions
        file_handler = logging.handlers.RotatingFileHandler(
            "logs/actions.log",
            maxBytes=self._parse_size("100MB"),
            backupCount=10
        )
        file_handler.setLevel(logging.INFO)
        file_formatter = PentestingFormatter()
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        self.loggers['actions'] = ActionLogger()
    
    def _setup_tool_loggers(self):
        """Setup tool-specific loggers"""
        tools = ['network_tools', 'vuln_scanner', 'exploit_tools', 
                'web_tools', 'password_tools', 'llm_manager']
        
        for tool in tools:
            logger = logging.getLogger(tool)
            logger.setLevel(logging.DEBUG)
            
            # Tool-specific file
            file_handler = logging.handlers.RotatingFileHandler(
                f"logs/{tool}.log",
                maxBytes=self._parse_size("50MB"),
                backupCount=5
            )
            file_handler.setLevel(logging.DEBUG)
            file_formatter = PentestingFormatter()
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
            
            self.loggers[tool] = logger
    
    def _setup_learning_logger(self):
        """Setup learning logger"""
        logger = logging.getLogger("learning")
        logger.setLevel(logging.INFO)
        
        # Learning-specific file
        file_handler = logging.handlers.RotatingFileHandler(
            "logs/learning.log",
            maxBytes=self._parse_size("100MB"),
            backupCount=10
        )
        file_handler.setLevel(logging.INFO)
        file_formatter = PentestingFormatter()
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        self.loggers['learning'] = logger
    
    def _parse_size(self, size_str: str) -> int:
        """Parse size string to bytes"""
        size_str = size_str.upper()
        if size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get logger by name"""
        with self.lock:
            return self.loggers.get(name, logging.getLogger(name))
    
    def get_action_logger(self) -> ActionLogger:
        """Get action logger"""
        return self.loggers['actions']
    
    def log_startup(self):
        """Log agent startup"""
        logger = self.get_logger('main')
        logger.info("=" * 80)
        logger.info("AUTONOMOUS AI PENTESTING AGENT STARTING")
        logger.info("=" * 80)
        logger.info(f"Configuration loaded from: {self.config.config_path}")
        logger.info(f"LLM Providers: {[p.name for p in self.config.llm_providers]}")
        logger.info(f"Database: {self.config.database.type}")
        logger.info(f"Autonomous mode: {self.config.agent.autonomous}")
        logger.info(f"Never ask: {self.config.agent.never_ask}")
        logger.info("=" * 80)
    
    def log_shutdown(self):
        """Log agent shutdown"""
        logger = self.get_logger('main')
        logger.info("=" * 80)
        logger.info("AUTONOMOUS AI PENTESTING AGENT SHUTTING DOWN")
        logger.info("=" * 80)
    
    def log_error(self, error: Exception, context: str = ""):
        """Log errors with context"""
        logger = self.get_logger('main')
        logger.error(f"ERROR in {context}: {str(error)}", exc_info=True)
    
    def log_performance(self, operation: str, duration: float, success: bool = True):
        """Log performance metrics"""
        logger = self.get_logger('main')
        status = "SUCCESS" if success else "FAILED"
        logger.info(f"PERFORMANCE: {operation} - {duration:.2f}s - {status}")


# Global logger manager instance
logger_manager = None


def get_logger_manager(config) -> LoggerManager:
    """Get or create logger manager"""
    global logger_manager
    
    if logger_manager is None:
        logger_manager = LoggerManager(config)
    
    return logger_manager


def get_logger(name: str) -> logging.Logger:
    """Get logger by name"""
    if logger_manager:
        return logger_manager.get_logger(name)
    else:
        return logging.getLogger(name)


def get_action_logger() -> ActionLogger:
    """Get action logger"""
    if logger_manager:
        return logger_manager.get_action_logger()
    else:
        return ActionLogger()
