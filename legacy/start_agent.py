#!/usr/bin/env python3
"""
Startup script for the Autonomous AI Pentesting Agent
Shows what's needed to run the agent and starts it
"""

import os
import sys
import asyncio
from agent.config_manager import ConfigManager
from agent.core import get_agent


def check_requirements():
    """Check if all requirements are met"""
    print("Checking requirements...")
    
    # Check MongoDB Atlas connection
    try:
        import pymongo
        config = ConfigManager()
        client = pymongo.MongoClient(config.get_connection_string(), serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        print("OK MongoDB Atlas connection: OK")
    except Exception as e:
        print(f"ERROR MongoDB Atlas connection: FAILED - {e}")
        print("  Set MONGODB_URL environment variable or update config.yaml")
        return False
    
    # Check LLM providers
    from agent.llm_manager import get_llm_manager
    llm_manager = get_llm_manager()
    status = llm_manager.get_provider_status()
    
    available_providers = 0
    for provider, info in status.items():
        if info['available']:
            print(f"OK {provider}: OK ({info['model']})")
            available_providers += 1
        else:
            print(f"ERROR {provider}: NOT AVAILABLE")
    
    if available_providers == 0:
        print("ERROR No LLM providers available")
        print("  Set API keys:")
        print("  - OpenAI: Already configured in config.yaml")
        print("  - Anthropic: export ANTHROPIC_API_KEY='your-key'")
        print("  - Gemini: export GEMINI_API_KEY='your-key'")
        return False
    
    print(f"OK {available_providers} LLM providers available")
    return True


async def start_agent():
    """Start the autonomous agent"""
    print("\n" + "="*60)
    print("STARTING AUTONOMOUS AI PENTESTING AGENT")
    print("="*60)
    print("WARNING: This agent operates autonomously without safety controls!")
    print("It will continuously scan and attack targets.")
    print("Use only in authorized testing environments.")
    print("="*60)
    
    try:
        config = ConfigManager()
        agent = await get_agent(config)
        
        print("Agent initialized successfully!")
        print("Starting autonomous operation...")
        
        # Start the agent
        await agent.start_autonomous_operation()
        
    except KeyboardInterrupt:
        print("\nAgent stopped by user.")
    except Exception as e:
        print(f"\nAgent error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main startup function"""
    print("AUTONOMOUS AI PENTESTING AGENT - STARTUP")
    print("="*50)
    
    if not check_requirements():
        print("\nRequirements not met. Please fix the issues above.")
        print("\nQuick setup:")
        print("1. MongoDB Atlas: Already configured")
        print("2. API Keys:")
        print("   - OpenAI: Already configured in config.yaml")
        print("   - Anthropic: export ANTHROPIC_API_KEY='your-key'")
        print("   - Gemini: export GEMINI_API_KEY='your-key'")
        print("\nExample:")
        print("export ANTHROPIC_API_KEY='your-anthropic-key'")
        print("export GEMINI_API_KEY='your-gemini-key'")
        print("python3 start_agent.py")
        sys.exit(1)
    
    # Start the agent
    asyncio.run(start_agent())


if __name__ == "__main__":
    main()
