"""
Configuration management system for the autonomous AI pentesting agent
"""

import yaml
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class LLMProvider:
    """Configuration for an LLM provider"""
    name: str
    model: str
    api_key_env: Optional[str] = None
    api_keys: Optional[List[str]] = None
    endpoint: Optional[str] = None
    max_tokens: int = 4000
    temperature: float = 0.7
    priority: int = 1


@dataclass
class AgentConfig:
    """Main agent configuration"""
    autonomous: bool = True
    interactive_mode: bool = False
    never_ask: bool = True
    continuous_mode: bool = True
    max_iterations: str = "unlimited"
    decision_timeout: int = 30
    retry_attempts: int = 5
    escalation_threshold: int = 10


@dataclass
class NetworkConfig:
    """Network scanning configuration"""
    scan_interval: int = 300
    scan_ranges: List[str] = None
    aggressive_scan: bool = True
    stealth_mode: bool = False
    
    def __post_init__(self):
        if self.scan_ranges is None:
            self.scan_ranges = ["auto"]


@dataclass
class LearningConfig:
    """Self-learning configuration"""
    fine_tune_interval: int = 86400
    min_experiences: int = 100
    success_threshold: float = 0.7
    learning_rate: float = 0.001
    batch_size: int = 32


@dataclass
class DatabaseConfig:
    """Database configuration for MongoDB Atlas"""
    type: str = "mongodb"
    database: str = "ai_pentesting_agent"
    username: str = ""
    password: str = ""
    auth_source: str = "admin"
    connection_string: str = ""
    collections: Dict[str, str] = None
    
    def __post_init__(self):
        if self.collections is None:
            self.collections = {
                "experiences": "experiences",
                "targets": "targets", 
                "exploits": "exploits",
                "sessions": "sessions"
            }


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    file: str = "logs/agent.log"
    max_size: str = "100MB"
    backup_count: int = 5


@dataclass
class ExploitationConfig:
    """Exploitation configuration"""
    timeout: int = 300
    max_concurrent: int = 5
    aggressive_mode: bool = True
    custom_exploit_generation: bool = True


@dataclass
class SafetyConfig:
    """Safety configuration (disabled as requested)"""
    enabled: bool = False
    target_whitelist: List[str] = None
    kill_switch: bool = False
    
    def __post_init__(self):
        if self.target_whitelist is None:
            self.target_whitelist = []


class ConfigManager:
    """Manages configuration loading and validation"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config_data = self._load_config()
        
        # Initialize configuration objects
        self.llm_providers = self._parse_llm_providers()
        self.agent = AgentConfig(**self.config_data.get("agent", {}))
        self.network = NetworkConfig(**self.config_data.get("network", {}))
        self.learning = LearningConfig(**self.config_data.get("learning", {}))
        self.database = DatabaseConfig(**self.config_data.get("database", {}))
        self.logging = LoggingConfig(**self.config_data.get("logging", {}))
        self.exploitation = ExploitationConfig(**self.config_data.get("exploitation", {}))
        self.safety = SafetyConfig(**self.config_data.get("safety", {}))
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            print(f"Config file {self.config_path} not found. Using default configuration.")
            return {}
        except yaml.YAMLError as e:
            print(f"Error parsing config file: {e}")
            return {}
    
    def _parse_llm_providers(self) -> List[LLMProvider]:
        """Parse LLM provider configurations"""
        providers = []
        llm_config = self.config_data.get("llm", {}).get("providers", [])
        
        for provider_config in llm_config:
            provider = LLMProvider(**provider_config)
            providers.append(provider)
        
        # Sort by priority
        providers.sort(key=lambda x: x.priority)
        return providers
    
    def get_primary_llm_provider(self) -> LLMProvider:
        """Get the highest priority LLM provider"""
        if self.llm_providers:
            return self.llm_providers[0]
        raise ValueError("No LLM providers configured")
    
    def get_llm_provider_by_name(self, name: str) -> Optional[LLMProvider]:
        """Get LLM provider by name"""
        for provider in self.llm_providers:
            if provider.name == name:
                return provider
        return None
    
    def validate_config(self) -> bool:
        """Validate the configuration"""
        try:
            # Check if at least one LLM provider is configured
            if not self.llm_providers:
                print("Error: No LLM providers configured")
                return False
            
            # Check API keys for providers that need them
            for provider in self.llm_providers:
                if provider.api_key_env and not os.getenv(provider.api_key_env):
                    print(f"Warning: API key environment variable {provider.api_key_env} not set for {provider.name}")
            
            # Validate database configuration
            if self.database.type not in ["mongodb", "sqlite", "postgresql"]:
                print(f"Error: Unsupported database type: {self.database.type}")
                return False
            
            return True
        except Exception as e:
            print(f"Configuration validation error: {e}")
            return False
    
    def reload_config(self):
        """Reload configuration from file"""
        self.config_data = self._load_config()
        self.llm_providers = self._parse_llm_providers()
        # Re-initialize other config objects
        self.agent = AgentConfig(**self.config_data.get("agent", {}))
        self.network = NetworkConfig(**self.config_data.get("network", {}))
        self.learning = LearningConfig(**self.config_data.get("learning", {}))
        self.database = DatabaseConfig(**self.config_data.get("database", {}))
        self.logging = LoggingConfig(**self.config_data.get("logging", {}))
        self.exploitation = ExploitationConfig(**self.config_data.get("exploitation", {}))
        self.safety = SafetyConfig(**self.config_data.get("safety", {}))
    
    def get_connection_string(self) -> str:
        """Get MongoDB Atlas connection string"""
        # Check if full connection string is provided (MongoDB Atlas recommended)
        if hasattr(self.database, 'connection_string') and self.database.connection_string:
            return self.database.connection_string
            
        # Check for environment variables first
        mongodb_url = os.getenv('MONGODB_URL')
        if mongodb_url:
            return mongodb_url
            
        # Build MongoDB Atlas connection string from components
        if self.database.type == "mongodb":
            # Get individual components from environment or config
            database = os.getenv('MONGODB_DATABASE', self.database.database)
            username = os.getenv('MONGODB_USERNAME', getattr(self.database, 'username', ''))
            password = os.getenv('MONGODB_PASSWORD', getattr(self.database, 'password', ''))
            auth_source = os.getenv('MONGODB_AUTH_SOURCE', getattr(self.database, 'auth_source', 'admin'))
            
            # For MongoDB Atlas, require username and password
            if username and password:
                # Use MongoDB Atlas format
                cluster = os.getenv('MONGODB_CLUSTER', 'your-cluster')
                return f"mongodb+srv://{username}:{password}@{cluster}.mongodb.net/{database}?retryWrites=true&w=majority&authSource={auth_source}"
            else:
                raise ValueError("MongoDB Atlas requires username and password. Please configure them in config.yaml or environment variables.")
        elif self.database.type == "sqlite":
            return f"sqlite:///{self.database.database}.db"
        elif self.database.type == "postgresql":
            return f"postgresql://{self.database.host}:{self.database.port}/{self.database.database}"
        else:
            raise ValueError(f"Unsupported database type: {self.database.type}")


# Global configuration instance
config = ConfigManager()
