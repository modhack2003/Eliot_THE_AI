#!/usr/bin/env python3
"""
Interactive Pentesting Agent Entry Point
Chat-based interface powered by Gemini 2.5 Pro
"""

import os
import asyncio
import sys
import warnings
from agent.interactive_agent import InteractivePentestingAgent

# Hide all warnings and stderr messages
warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['GEMINI_LOG_LEVEL'] = 'ERROR'

# Redirect stderr to suppress Google API warnings
class SuppressStderr:
    def __init__(self):
        self.original_stderr = sys.stderr
    
    def __enter__(self):
        sys.stderr = open(os.devnull, 'w')
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stderr.close()
        sys.stderr = self.original_stderr

def print_banner():
    """Print beautiful welcome banner"""
    banner = """
================================================================================
                                                                                
                        E L I O T                                              
                                                                                
                    H A C K E R   A S S I S T A N T                           
                                                                                
                         by Bikram@2003                                        
                                                                                
  +----------------------------------------------------------------------------+
  |                        INTERACTIVE HACKER ASSISTANT                       |
  |                                                                            |
  |  * Network Scanning & Discovery                                           |
  |  * Vulnerability Assessment                                               |
  |  * Exploitation & Post-Exploitation                                       |
  |  * Web Application Testing                                                |
  |  * Password Cracking & Brute Force                                        |
  |  * AI-Powered Intelligence & Analysis                                     |
  +----------------------------------------------------------------------------+
                                                                                
  [INFO] Type 'help' for commands  |  Type 'quit', 'exit', or 'bye' to exit    
                                                                                
================================================================================
"""
    print(banner)

async def main():
    """Main entry point for interactive mode"""
    
    # Suppress all warnings and stderr during initialization
    with SuppressStderr():
        print_banner()
        
        # Set MongoDB Atlas URL
        os.environ['MONGODB_URL'] = 'mongodb+srv://bikram20031213:2dYTwXlrYpgpyGxC@cluster0.8zrf3zz.mongodb.net/ai_pentesting_agent'
        
        try:
            # Create and start interactive agent
            agent = InteractivePentestingAgent()
            await agent.start_chat()
            
        except KeyboardInterrupt:
            print("\n\n[EXIT] Goodbye! Remember to stay ethical in your testing.")
            sys.exit(0)
        except Exception as e:
            print(f"\n[ERROR] Fatal error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
