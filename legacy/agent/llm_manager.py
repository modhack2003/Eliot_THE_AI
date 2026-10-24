"""
LLM Manager for multi-provider support with dynamic switching and API key rotation
Supports OpenAI, Anthropic, Gemini, and Ollama with automatic failover
"""

import os
import sys
import time
import random
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class TaskComplexity(Enum):
    """Task complexity levels for LLM selection"""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    CRITICAL = "critical"

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    # Suppress warnings before importing Gemini
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from .config_manager import ConfigManager


class ProviderType(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"


@dataclass
class APIKeyStatus:
    """Track API key usage and status"""
    key: str
    usage_count: int = 0
    last_used: float = 0
    rate_limited_until: float = 0
    is_active: bool = True
    error_count: int = 0


@dataclass
class LLMResponse:
    """Standardized LLM response"""
    content: str
    provider: str
    model: str
    tokens_used: int = 0
    cost: float = 0.0
    latency: float = 0.0


class LLMManager:
    """Advanced LLM manager with API key rotation and provider failover"""
    
    def __init__(self, config=None):
        self.config = config or ConfigManager()
        self.logger = logging.getLogger("llm_manager")
        self.providers = {}
        self.api_key_status = {}
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize all configured providers"""
        llm_providers_config = self.config.config_data.get('llm', {}).get('providers', [])
        
        for provider_config in llm_providers_config:
            name = provider_config.get('name')
            model = provider_config.get('model')
            
            if name == 'openai':
                if OPENAI_AVAILABLE:
                    self._setup_openai_provider(provider_config)
                else:
                    self.logger.warning(f"OpenAI library not installed")
            elif name == 'anthropic':
                if ANTHROPIC_AVAILABLE:
                    self._setup_anthropic_provider(provider_config)
                else:
                    self.logger.warning(f"Anthropic library not installed")
            elif name == 'gemini':
                if GEMINI_AVAILABLE:
                    self._setup_gemini_provider(provider_config)
                else:
                    self.logger.warning(f"Gemini library not installed")
            elif name == 'ollama':
                self._setup_ollama_provider(provider_config)
    
    def _setup_openai_provider(self, config):
        """Setup OpenAI provider with multiple API keys"""
        api_keys = config.get('api_keys', [])
        if not api_keys:
            # Fallback to environment variable
            env_key = os.getenv('OPENAI_API_KEY')
            if env_key:
                api_keys = [env_key]
        
        if not api_keys:
            self.logger.warning("No OpenAI API keys configured")
            return
        
        # Initialize API key status tracking
        for key in api_keys:
            self.api_key_status[key] = APIKeyStatus(key=key)
        
        self.providers['openai'] = {
            'type': ProviderType.OPENAI,
            'model': config.get('model', 'gpt-4o'),
            'api_keys': api_keys,
            'max_tokens': config.get('max_tokens', 4000),
            'temperature': config.get('temperature', 0.7),
            'priority': config.get('priority', 1)
        }
        
        self.logger.info(f"OpenAI provider initialized with {len(api_keys)} API keys")
    
    def _setup_anthropic_provider(self, config):
        """Setup Anthropic provider"""
        api_key_env = config.get('api_key_env', 'ANTHROPIC_API_KEY')
        api_key = os.getenv(api_key_env)
        
        if not api_key:
            self.logger.warning(f"Anthropic API key not found in {api_key_env}")
            return
        
        self.providers['anthropic'] = {
            'type': ProviderType.ANTHROPIC,
            'model': config.get('model', 'claude-3-5-sonnet-20241022'),
            'api_key': api_key,
            'max_tokens': config.get('max_tokens', 4000),
            'temperature': config.get('temperature', 0.7),
            'priority': config.get('priority', 2)
        }
        
        self.logger.info("Anthropic provider initialized")
    
    def _setup_gemini_provider(self, config):
        """Setup Gemini provider with multiple API keys"""
        api_keys = config.get('api_keys', [])
        if not api_keys:
            # Fallback to environment variable
            api_key_env = config.get('api_key_env', 'GEMINI_API_KEY')
            env_key = os.getenv(api_key_env)
            if env_key:
                api_keys = [env_key]
        
        if not api_keys:
            self.logger.warning("No Gemini API keys configured")
            return
        
        # Initialize API key status tracking
        for key in api_keys:
            self.api_key_status[key] = APIKeyStatus(key=key)
        
        try:
            genai.configure(api_key=api_keys[0])  # Use first key for configuration
            self.providers['gemini'] = {
                'type': ProviderType.GEMINI,
                'model': config.get('model', 'gemini-2.5-pro'),
                'api_keys': api_keys,
                'max_tokens': config.get('max_tokens', 4000),
                'temperature': config.get('temperature', 0.7),
                'priority': config.get('priority', 1)
            }
            self.logger.info(f"Gemini provider initialized with {len(api_keys)} API keys")
        except Exception as e:
            self.logger.error(f"Failed to initialize Gemini: {e}")
    
    def _setup_ollama_provider(self, config):
        """Setup Ollama provider"""
        self.providers['ollama'] = {
            'type': ProviderType.OLLAMA,
            'model': config.get('model', 'llama3'),
            'endpoint': config.get('endpoint', 'http://localhost:11434'),
            'max_tokens': config.get('max_tokens', 4000),
            'temperature': config.get('temperature', 0.7),
            'priority': config.get('priority', 4)
        }
        
        self.logger.info("Ollama provider initialized")
    
    def _get_best_api_key(self, provider_name: str) -> Optional[str]:
        """Get the best available API key for providers with multiple keys"""
        if provider_name not in ['openai', 'gemini']:
            return None
        
        provider = self.providers.get(provider_name)
        if not provider:
            return None
        
        api_keys = provider.get('api_keys', [])
        if not api_keys:
            return None
        
        # Filter active keys that aren't rate limited
        current_time = time.time()
        available_keys = []
        
        for key in api_keys:
            status = self.api_key_status.get(key)
            if not status:
                continue
            
            if status.is_active and status.rate_limited_until < current_time:
                available_keys.append((key, status))
        
        if not available_keys:
            self.logger.warning(f"No available {provider_name} API keys")
            return None
        
        # Sort by usage count (prefer less used keys)
        available_keys.sort(key=lambda x: x[1].usage_count)
        
        return available_keys[0][0]
    
    def _mark_key_used(self, key: str, success: bool = True):
        """Mark an API key as used"""
        if key not in self.api_key_status:
            return
        
        status = self.api_key_status[key]
        status.usage_count += 1
        status.last_used = time.time()
        
        if not success:
            status.error_count += 1
            if status.error_count >= 3:
                # Rate limit for 1 hour after 3 errors
                status.rate_limited_until = time.time() + 3600
                self.logger.warning(f"API key rate limited due to errors: {key[:10]}...")
        else:
            status.error_count = 0
    
    def _get_provider_by_priority(self) -> Optional[str]:
        """Get provider by priority order"""
        if not self.providers:
            return None
        
        # Sort providers by priority
        sorted_providers = sorted(
            self.providers.items(),
            key=lambda x: x[1]['priority']
        )
        
        return sorted_providers[0][0]
    
    def generate_text(self, prompt: str, provider: Optional[str] = None, **kwargs) -> Optional[LLMResponse]:
        """Generate text using the best available provider"""
        start_time = time.time()
        
        # Determine which provider to use
        if not provider:
            provider = self._get_provider_by_priority()
        
        if not provider:
            self.logger.error("No LLM providers available")
            return None
        
        # Try the requested provider first, then fallback to others
        providers_to_try = [provider]
        if provider != self._get_provider_by_priority():
            providers_to_try.append(self._get_provider_by_priority())
        
        # Add all other providers as fallbacks
        for p_name in self.providers.keys():
            if p_name not in providers_to_try:
                providers_to_try.append(p_name)
        
        for current_provider in providers_to_try:
            try:
                response = self._call_provider(current_provider, prompt, **kwargs)
                if response:
                    response.latency = time.time() - start_time
                    return response
            except Exception as e:
                self.logger.warning(f"Provider {current_provider} failed: {e}")
                continue
        
        self.logger.error("All LLM providers failed")
        return None
    
    def generate_response(self, prompt: str, provider: Optional[str] = None, **kwargs) -> Optional[str]:
        """Generate response text (alias for generate_text for compatibility)"""
        response = self.generate_text(prompt, provider, **kwargs)
        return response.content if response else None
    
    def _call_provider(self, provider_name: str, prompt: str, **kwargs) -> Optional[LLMResponse]:
        """Call specific provider"""
        provider = self.providers.get(provider_name)
        if not provider:
            return None
        
        try:
            if provider['type'] == ProviderType.OPENAI:
                return self._call_openai(provider, prompt, **kwargs)
            elif provider['type'] == ProviderType.ANTHROPIC:
                return self._call_anthropic(provider, prompt, **kwargs)
            elif provider['type'] == ProviderType.GEMINI:
                return self._call_gemini(provider, prompt, **kwargs)
            elif provider['type'] == ProviderType.OLLAMA:
                return self._call_ollama(provider, prompt, **kwargs)
        except Exception as e:
            self.logger.error(f"Provider {provider_name} call failed: {e}")
            return None
    
    def _call_openai(self, provider: dict, prompt: str, **kwargs) -> Optional[LLMResponse]:
        """Call OpenAI API with key rotation"""
        api_key = self._get_best_api_key('openai')
        if not api_key:
            raise Exception("No available OpenAI API keys")
        
        try:
            client = openai.OpenAI(api_key=api_key)
            
            response = client.chat.completions.create(
                model=provider['model'],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=provider['max_tokens'],
                temperature=provider['temperature'],
                **kwargs
            )
            
            self._mark_key_used(api_key, success=True)
            
            return LLMResponse(
                content=response.choices[0].message.content,
                provider='openai',
                model=provider['model'],
                tokens_used=response.usage.total_tokens if response.usage else 0
            )
            
        except Exception as e:
            self._mark_key_used(api_key, success=False)
            raise e
    
    def _call_anthropic(self, provider: dict, prompt: str, **kwargs) -> Optional[LLMResponse]:
        """Call Anthropic API"""
        client = anthropic.Anthropic(api_key=provider['api_key'])
        
        response = client.messages.create(
            model=provider['model'],
            max_tokens=provider['max_tokens'],
            messages=[{"role": "user", "content": prompt}],
            temperature=provider['temperature'],
            **kwargs
        )
        
        return LLMResponse(
            content=response.content[0].text,
            provider='anthropic',
            model=provider['model'],
            tokens_used=response.usage.input_tokens + response.usage.output_tokens
        )
    
    def _call_gemini(self, provider: dict, prompt: str, **kwargs) -> Optional[LLMResponse]:
        """Call Gemini API with key rotation"""
        api_keys = provider.get('api_keys', [])
        if not api_keys:
            # Fallback to single API key
            api_key = provider.get('api_key')
            if not api_key:
                raise Exception("No Gemini API keys available")
            api_keys = [api_key]
        
        # Try each available API key, sorted by usage count (least used first)
        current_time = time.time()
        available_keys = []
        
        for key in api_keys:
            status = self.api_key_status.get(key)
            if not status:
                continue
            
            if status.is_active and status.rate_limited_until < current_time:
                available_keys.append((key, status))
        
        if not available_keys:
            raise Exception("No available Gemini API keys")
        
        # Sort by usage count (prefer less used keys)
        available_keys.sort(key=lambda x: x[1].usage_count)
        
        for key, status in available_keys:
            
            try:
                # Configure with current key (suppress warnings)
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    genai.configure(api_key=key)
                    model = genai.GenerativeModel(provider['model'])
                    
                    response = model.generate_content(
                        prompt,
                        generation_config=genai.types.GenerationConfig(
                            max_output_tokens=provider['max_tokens'],
                            temperature=provider['temperature']
                        )
                    )
                
                self._mark_key_used(key, success=True)
                
                return LLMResponse(
                    content=response.text,
                    provider='gemini',
                    model=provider['model'],
                    tokens_used=len(response.text.split())  # Approximate
                )
                
            except Exception as e:
                error_msg = str(e)
                
                # Check for quota exceeded errors
                if "quota" in error_msg.lower() or "429" in error_msg:
                    # Mark key as rate limited for 24 hours
                    status.rate_limited_until = time.time() + 86400  # 24 hours
                    self.logger.warning(f"Gemini API key {key[:10]}... quota exceeded, rate limiting for 24 hours")
                    # Note: Status message will be shown separately in main interface
                else:
                    # Regular error, mark as failed
                    self._mark_key_used(key, success=False)
                    self.logger.warning(f"Gemini API key {key[:10]}... failed: {e}")
                
                continue  # Try next key instead of raising immediately
        
        raise Exception("All Gemini API keys failed or are rate limited. Daily quota exceeded for all keys.")
    
    def _call_ollama(self, provider: dict, prompt: str, **kwargs) -> Optional[LLMResponse]:
        """Call Ollama API"""
        import requests
        
        url = f"{provider['endpoint']}/api/generate"
        data = {
            "model": provider['model'],
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": provider['temperature'],
                "num_predict": provider['max_tokens']
            }
        }
        
        response = requests.post(url, json=data, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        
        return LLMResponse(
            content=result.get('response', ''),
            provider='ollama',
            model=provider['model']
        )
    
    def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all providers"""
        status = {}
        
        for name, provider in self.providers.items():
            provider_status = {
                'available': True,
                'model': provider['model'],
                'priority': provider['priority']
            }
            
            if name == 'openai':
                api_keys = provider['api_keys']
                available_keys = sum(1 for key in api_keys 
                                   if self.api_key_status.get(key, APIKeyStatus(key='')).is_active)
                provider_status['api_keys_total'] = len(api_keys)
                provider_status['api_keys_available'] = available_keys
            elif name in ['anthropic', 'gemini']:
                provider_status['api_key_configured'] = bool(provider.get('api_key'))
            
            status[name] = provider_status
        
        return status
    
    def reset_api_key_errors(self):
        """Reset error counts for all API keys"""
        for status in self.api_key_status.values():
            status.error_count = 0
            status.rate_limited_until = 0
            status.is_active = True
        
        self.logger.info("API key error counts reset")


# Global LLM manager instance (will be initialized with config when needed)
llm_manager = None

def get_llm_manager(config=None):
    """Get or create LLM manager instance"""
    global llm_manager
    if llm_manager is None:
        llm_manager = LLMManager(config)
    return llm_manager