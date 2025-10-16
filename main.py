#!/usr/bin/env python3
"""
Autonomous AI Pentesting Agent for Kali Linux
Main entry point with continuous autonomous loop and error recovery
"""

import asyncio
import signal
import sys
import os
import time
import logging
from typing import Optional
import traceback

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.config_manager import ConfigManager
from agent.core import get_agent
from agent.persistence.logger import get_logger_manager
from agent.autonomous_workflow import OptimizedAutonomousWorkflow


class AgentRunner:
    """Main agent runner with error recovery and monitoring"""
    
    def __init__(self):
        self.config = None
        self.logger_manager = None
        self.agent = None
        self.running = False
        self.restart_count = 0
        self.max_restarts = 10
        self.restart_delay = 30  # seconds
        
    async def initialize(self):
        """Initialize the agent runner"""
        try:
            # Load configuration
            self.config = ConfigManager()
            
            # Validate configuration
            if not self.config.validate_config():
                print("Configuration validation failed!")
                return False
            
            # Initialize logging
            self.logger_manager = get_logger_manager(self.config)
            self.logger_manager.log_startup()
            
            # Initialize agent
            self.agent = await get_agent(self.config)
            
            # Initialize optimized workflow
            self.workflow = OptimizedAutonomousWorkflow(self.agent)
            
            self.logger_manager.get_logger('main').info("Agent runner initialized successfully")
            return True
            
        except Exception as e:
            print(f"Initialization failed: {e}")
            traceback.print_exc()
            return False
    
    async def start(self):
        """Start the autonomous agent"""
        try:
            self.running = True
            self.logger_manager.get_logger('main').info("Starting autonomous AI pentesting agent...")
            
            # Set up signal handlers
            self._setup_signal_handlers()
            
            # Start optimized workflow instead of continuous loop
            await self.workflow.run_workflow()
            
        except Exception as e:
            self.logger_manager.get_logger('main').error(f"Agent start failed: {e}")
            traceback.print_exc()
            raise
    
    async def stop(self):
        """Stop the autonomous agent"""
        try:
            self.running = False
            self.logger_manager.get_logger('main').info("Stopping autonomous AI pentesting agent...")
            
            if self.agent:
                await self.agent.stop_operation()
            
            self.logger_manager.log_shutdown()
            
        except Exception as e:
            self.logger_manager.get_logger('main').error(f"Agent stop failed: {e}")
    
    async def run_with_recovery(self):
        """Run agent with automatic recovery"""
        while self.running and self.restart_count < self.max_restarts:
            try:
                await self.start()
                
                # If we get here, the agent stopped normally
                self.logger_manager.get_logger('main').info("Agent stopped normally")
                break
                
            except KeyboardInterrupt:
                self.logger_manager.get_logger('main').info("Received keyboard interrupt")
                break
                
            except Exception as e:
                self.restart_count += 1
                self.logger_manager.get_logger('main').error(
                    f"Agent crashed (restart {self.restart_count}/{self.max_restarts}): {e}"
                )
                traceback.print_exc()
                
                if self.restart_count < self.max_restarts:
                    self.logger_manager.get_logger('main').info(
                        f"Restarting in {self.restart_delay} seconds..."
                    )
                    await asyncio.sleep(self.restart_delay)
                    
                    # Reinitialize agent and workflow
                    try:
                        self.agent = await get_agent(self.config)
                        self.workflow = OptimizedAutonomousWorkflow(self.agent)
                    except Exception as init_error:
                        self.logger_manager.get_logger('main').error(
                            f"Reinitialization failed: {init_error}"
                        )
                        break
                else:
                    self.logger_manager.get_logger('main').error(
                        "Maximum restart attempts reached. Agent will not restart."
                    )
                    break
        
        # Final cleanup
        await self.stop()
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            self.logger_manager.get_logger('main').info(f"Received signal {signum}")
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def monitor_agent(self):
        """Monitor agent health and performance"""
        while self.running:
            try:
                if self.agent:
                    # Get agent status
                    status = self.agent.get_agent_status()
                    
                    # Log status periodically
                    self.logger_manager.get_logger('main').info(
                        f"Agent Status: {status['state']}, "
                        f"Targets: {status['context_size']['targets']}, "
                        f"Sessions: {status['active_sessions']}, "
                        f"Uptime: {status['statistics']['uptime']:.1f}s"
                    )
                    
                    # Check for issues
                    if status['statistics']['exploits_attempted'] > 1000:
                        self.logger_manager.get_logger('main').warning(
                            "High number of exploit attempts detected"
                        )
                
                # Wait before next check
                await asyncio.sleep(300)  # 5 minutes
                
            except Exception as e:
                self.logger_manager.get_logger('main').error(f"Monitoring error: {e}")
                await asyncio.sleep(60)


def print_banner():
    """Print agent banner"""
    banner = """
    ================================================================
    |                                                              |
    |                        E L I O T                            |
    |                                                              |
    |              AUTONOMOUS HACKER AGENT                        |
    |                                                              |
    |                         by Bikram@2003                      |
    |                                                              |
    |  FEATURES:                                                   |
    |  * MINIMAL TOKEN USAGE - Long-term operation                |
    |  * SMART FAILURE HANDLING - Different methods on failure    |
    |  * LIMITED CYCLES - No infinite loops                       |
    |  * RULE-BASED APPROACH - Reduced AI dependency              |
    |  * TARGET HANDOFF - Receives targets from interactive mode  |
    |                                                              |
    |  WORKFLOW: Initialize -> Scan -> Analyze -> Exploit -> Learn |
    |  MAX CYCLES: 10 (prevents infinite loops)                   |
    |                                                              |
    |  USER ASSUMES ALL LEGAL RESPONSIBILITY                      |
    |                                                              |
    ================================================================
    """
    print(banner)


def check_requirements():
    """Check system requirements"""
    try:
        # Check if running on Windows (since this is a demo)
        import platform
        if platform.system() == "Windows":
            print("INFO: Running on Windows - this is a demo environment")
            print("   For full functionality, deploy on Kali Linux")
        
        # Check for required tools (skip on Windows demo)
        if platform.system() != "Windows":
            required_tools = [
                'nmap', 'metasploit-framework', 'sqlmap', 'hydra', 
                'john', 'hashcat', 'dirb', 'gobuster', 'nikto'
            ]
            
            missing_tools = []
            for tool in required_tools:
                if not os.system(f"which {tool} > /dev/null 2>&1") == 0:
                    missing_tools.append(tool)
            
            if missing_tools:
                print(f"WARNING: Missing tools: {', '.join(missing_tools)}")
                print("   Install with: sudo apt update && sudo apt install -y " + " ".join(missing_tools))
            
            # Check for MongoDB
            if not os.system("which mongod > /dev/null 2>&1") == 0:
                print("WARNING: MongoDB not found")
                print("   Install with: sudo apt install -y mongodb")
        
        # Check for Python packages
        try:
            import pymongo
            import requests
            import yaml
            print("Python dependencies: OK")
        except ImportError as e:
            print(f"WARNING: Missing Python package: {e}")
            print("   Install with: pip install -r requirements.txt")
        
    except Exception as e:
        print(f"Could not check requirements: {e}")


def print_usage():
    """Print usage information"""
    print("\nUsage:")
    print("  python3 main.py                    # Start autonomous agent")
    print("  python3 main.py --help             # Show this help")
    print("  python3 main.py --check            # Check requirements only")
    print("  python3 main.py --config <file>    # Use custom config file")
    print("\nEnvironment Variables:")
    print("  OPENAI_API_KEY                     # OpenAI API key")
    print("  ANTHROPIC_API_KEY                  # Anthropic API key")
    print("\nConfiguration:")
    print("  Edit config.yaml to customize agent behavior")
    print("  All safety controls are DISABLED by default")
    print("\nLogs:")
    print("  logs/agent.log                     # Main agent log")
    print("  logs/actions.log                   # Action log")
    print("  logs/*.log                         # Component logs")


async def main():
    """Main entry point"""
    try:
        # Set MongoDB Atlas URL
        os.environ['MONGODB_URL'] = 'mongodb+srv://bikram20031213:2dYTwXlrYpgpyGxC@cluster0.8zrf3zz.mongodb.net/ai_pentesting_agent'
        
        # Parse command line arguments
        if len(sys.argv) > 1:
            if sys.argv[1] == '--help':
                print_usage()
                return
            elif sys.argv[1] == '--check':
                check_requirements()
                return
            elif sys.argv[1] == '--config' and len(sys.argv) > 2:
                config_file = sys.argv[2]
                os.environ['CONFIG_FILE'] = config_file
        
        # Print banner
        print_banner()
        
        # Check requirements
        check_requirements()
        
        # Confirm user understands the risks
        print("\n" + "="*70)
        print("CRITICAL WARNING: THIS AGENT IS FULLY AUTONOMOUS")
        print("   - No safety controls or human oversight")
        print("   - Will attack any reachable targets")
        print("   - Never asks for permission")
        print("   - Use only in controlled environments")
        print("   - User assumes ALL legal responsibility")
        print("="*70)
        
        response = input("\nDo you understand the risks and want to continue? (yes/NO): ")
        if response.lower() != 'yes':
            print("Agent startup cancelled.")
            return
        
        # Initialize and run agent
        runner = AgentRunner()
        
        # Try to initialize
        if not await runner.initialize():
            print("Failed to initialize agent. Please check your configuration.")
            print("Make sure MongoDB is running and API keys are set.")
            print("You can run 'python3 main.py --check' to verify requirements.")
            return
        
        # Start monitoring task
        monitor_task = asyncio.create_task(runner.monitor_agent())
        
        # Run agent with recovery
        await runner.run_with_recovery()
        
        # Cancel monitoring task
        monitor_task.cancel()
        
    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt. Shutting down...")
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Set up asyncio event loop
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Run main function
    asyncio.run(main())
