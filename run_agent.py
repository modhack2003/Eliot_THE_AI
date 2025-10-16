#!/usr/bin/env python3
"""
Run the Autonomous AI Pentesting Agent with proper configuration
"""

import os
import asyncio
from agent.config_manager import ConfigManager
from agent.core import get_agent


async def main():
    """Main entry point"""
    print("AUTONOMOUS AI PENTESTING AGENT")
    print("="*50)
    
    # Set MongoDB Atlas URL
    os.environ['MONGODB_URL'] = 'mongodb+srv://bikram20031213:2dYTwXlrYpgpyGxC@cluster0.8zrf3zz.mongodb.net/ai_pentesting_agent'
    
    print("WARNING: This agent operates autonomously without safety controls!")
    print("It will continuously scan and attack targets.")
    print("Use only in authorized testing environments.")
    print("="*50)
    
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


if __name__ == "__main__":
    asyncio.run(main())
