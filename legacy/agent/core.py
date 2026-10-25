"""
Main autonomous agent core with LLM-based reasoning and decision making
"""

import asyncio
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import json
from enum import Enum

from .llm_manager import LLMManager, TaskComplexity
from .persistence.database import get_database, Experience, Target, Session
from .persistence.logger import get_logger_manager, get_action_logger
from .targets.scanner import get_scanner
from .targets.profiler import get_profiler
from .intelligence.exploit_searcher import exploit_searcher
from .intelligence.web_researcher import web_researcher
from .exploit_dev.generator import get_exploit_generator
from .tools.exploit_tools import exploit_tools
from .tools.password_tools import password_tools
from .tools.web_tools import web_tools
from .config_manager import ConfigManager


class AgentState(Enum):
    """Agent operational states"""
    INITIALIZING = "initializing"
    DISCOVERING = "discovering"
    PROFILING = "profiling"
    RESEARCHING = "researching"
    EXPLOITING = "exploiting"
    LEARNING = "learning"
    ERROR = "error"


@dataclass
class Decision:
    """Agent decision"""
    action: str
    target: str
    reasoning: str
    confidence: float
    parameters: Dict[str, Any]
    timestamp: float


@dataclass
class Mission:
    """Mission objective"""
    objective: str
    targets: List[str]
    priority: int
    deadline: Optional[float] = None
    success_criteria: List[str] = None
    
    def __post_init__(self):
        if self.success_criteria is None:
            self.success_criteria = []


class AutonomousAgent:
    """Main autonomous AI pentesting agent"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.logger = logging.getLogger("autonomous_agent")
        self.action_logger = get_action_logger()
        
        # Core components
        self.llm_manager = None
        self.db = None
        self.scanner = None
        self.profiler = None
        self.exploit_generator = None
        
        # Agent state
        self.state = AgentState.INITIALIZING
        self.running = False
        self.current_mission = None
        self.active_sessions = []
        self.decision_history = []
        
        # Statistics
        self.stats = {
            "targets_discovered": 0,
            "targets_profiled": 0,
            "exploits_attempted": 0,
            "exploits_successful": 0,
            "sessions_established": 0,
            "missions_completed": 0,
            "uptime": 0
        }
        
        # Decision making context
        self.context = {
            "current_targets": [],
            "available_exploits": [],
            "learned_patterns": {},
            "failed_attempts": {},
            "successful_techniques": {}
        }
    
    async def initialize(self):
        """Initialize the autonomous agent"""
        try:
            self.logger.info("Initializing autonomous AI pentesting agent...")
            
            # Initialize core components
            self.llm_manager = LLMManager(self.config)
            self.db = await get_database()
            self.scanner = await get_scanner(self.config)
            self.profiler = await get_profiler(self.config)
            self.exploit_generator = await get_exploit_generator(self.llm_manager)
            
            # Load learned patterns
            await self._load_learned_patterns()
            
            self.state = AgentState.DISCOVERING
            self.logger.info("Agent initialization complete")
            
        except Exception as e:
            self.logger.error(f"Agent initialization failed: {e}")
            self.state = AgentState.ERROR
            raise
    
    async def start_autonomous_operation(self):
        """Start autonomous operation"""
        try:
            self.running = True
            self.logger.info("Starting autonomous operation...")
            
            # Start all subsystems
            await self.scanner.start_continuous_scanning()
            await self.profiler.start_profiling()
            
            # Main autonomous loop
            await self._autonomous_loop()
            
        except Exception as e:
            self.logger.error(f"Autonomous operation failed: {e}")
            self.state = AgentState.ERROR
    
    async def stop_operation(self):
        """Stop autonomous operation"""
        try:
            self.running = False
            self.logger.info("Stopping autonomous operation...")
            
            # Stop subsystems
            await self.scanner.stop_scanning()
            await self.profiler.stop_profiling()
            
            # Save learned patterns
            await self._save_learned_patterns()
            
            self.logger.info("Autonomous operation stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping operation: {e}")
    
    async def _autonomous_loop(self):
        """Main autonomous decision-making loop"""
        while self.running:
            try:
                start_time = time.time()
                
                # Update context
                await self._update_context()
                
                # Make autonomous decision
                decision = await self._make_autonomous_decision()
                
                if decision:
                    # Execute decision
                    await self._execute_decision(decision)
                    
                    # Store decision
                    self.decision_history.append(decision)
                    
                    # Learn from outcome
                    await self._learn_from_decision(decision)
                
                # Update statistics
                self.stats["uptime"] += time.time() - start_time
                
                # Brief pause to prevent overwhelming
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Autonomous loop error: {e}")
                await asyncio.sleep(5)
    
    async def _update_context(self):
        """Update agent context with current information"""
        try:
            # Get current targets
            self.context["current_targets"] = await self.db.get_all_targets()
            
            # Get available exploits
            self.context["available_exploits"] = await self._get_available_exploits()
            
            # Update learned patterns
            await self._update_learned_patterns()
            
        except Exception as e:
            self.logger.error(f"Context update failed: {e}")
    
    async def _make_autonomous_decision(self) -> Optional[Decision]:
        """Make autonomous decision using LLM reasoning"""
        try:
            # Create decision prompt
            prompt = self._create_decision_prompt()
            
            # Get LLM reasoning
            response = self.llm_manager.generate_response(prompt)
            
            if not response:
                self.logger.error("No response from LLM")
                return None
            
            # Parse decision from response
            decision = self._parse_decision(response)
            
            if decision:
                self.logger.info(f"Made decision: {decision.action} on {decision.target}")
                return decision
            
            return None
            
        except Exception as e:
            self.logger.error(f"Decision making failed: {e}")
            return None
    
    def _create_decision_prompt(self) -> str:
        """Create prompt for autonomous decision making"""
        return f"""
You are an autonomous AI pentesting agent. Make the next decision based on the current situation.

CURRENT STATE: {self.state.value}
MISSION: {self.current_mission.objective if self.current_mission else "Continuous autonomous operation"}

CURRENT CONTEXT:
- Targets discovered: {len(self.context['current_targets'])}
- Available exploits: {len(self.context['available_exploits'])}
- Active sessions: {len(self.active_sessions)}
- Successful exploits: {self.stats['exploits_successful']}
- Failed exploits: {self.stats['exploits_attempted'] - self.stats['exploits_successful']}

AVAILABLE TARGETS:
{self._format_targets_for_prompt()}

AVAILABLE EXPLOITS:
{self._format_exploits_for_prompt()}

LEARNED PATTERNS:
{self._format_patterns_for_prompt()}

AGENT PHILOSOPHY:
- Never give up - always try multiple approaches
- Be aggressive and persistent
- Learn from every attempt
- Escalate techniques when initial attempts fail
- Generate custom exploits when standard ones fail
- Never ask for permission - operate fully autonomously

DECISION OPTIONS:
1. DISCOVER - Scan for new targets
2. PROFILE - Profile a discovered target
3. RESEARCH - Research vulnerabilities for a target
4. EXPLOIT - Attempt exploitation
5. ESCALATE - Escalate privileges on compromised system
6. PERSIST - Establish persistence
7. PIVOT - Move to new target
8. LEARN - Analyze and learn from recent attempts

Make a decision and provide reasoning. Format your response as:
DECISION: [action]
TARGET: [target_ip]
REASONING: [your reasoning]
CONFIDENCE: [0.0-1.0]
PARAMETERS: [json parameters]

Choose the most aggressive and effective next action:
"""
    
    def _format_targets_for_prompt(self) -> str:
        """Format targets for LLM prompt"""
        if not self.context["current_targets"]:
            return "No targets discovered yet"
        
        targets_info = []
        for target in self.context["current_targets"][:10]:  # Limit to 10
            info = f"- {target.ip}: {len(target.services)} services"
            if target.hostname:
                info += f" ({target.hostname})"
            if target.compromised:
                info += " [COMPROMISED]"
            targets_info.append(info)
        
        return "\n".join(targets_info)
    
    def _format_exploits_for_prompt(self) -> str:
        """Format exploits for LLM prompt"""
        if not self.context["available_exploits"]:
            return "No exploits available"
        
        exploits_info = []
        for exploit in self.context["available_exploits"][:10]:  # Limit to 10
            info = f"- {exploit['name']}: {exploit.get('description', 'No description')[:50]}..."
            if exploit.get('cve'):
                info += f" (CVE: {exploit['cve']})"
            exploits_info.append(info)
        
        return "\n".join(exploits_info)
    
    def _format_patterns_for_prompt(self) -> str:
        """Format learned patterns for LLM prompt"""
        if not self.context["learned_patterns"]:
            return "No patterns learned yet"
        
        patterns_info = []
        for pattern_name, pattern_data in list(self.context["learned_patterns"].items())[:5]:
            success_rate = pattern_data.get('success_rate', 0)
            usage_count = pattern_data.get('usage_count', 0)
            patterns_info.append(f"- {pattern_name}: {success_rate:.2f} success rate ({usage_count} uses)")
        
        return "\n".join(patterns_info)
    
    def _parse_decision(self, response: str) -> Optional[Decision]:
        """Parse decision from LLM response"""
        try:
            lines = response.split('\n')
            decision_data = {}
            
            for line in lines:
                if line.startswith('DECISION:'):
                    decision_data['action'] = line.split(':', 1)[1].strip().upper()
                elif line.startswith('TARGET:'):
                    decision_data['target'] = line.split(':', 1)[1].strip()
                elif line.startswith('REASONING:'):
                    decision_data['reasoning'] = line.split(':', 1)[1].strip()
                elif line.startswith('CONFIDENCE:'):
                    decision_data['confidence'] = float(line.split(':', 1)[1].strip())
                elif line.startswith('PARAMETERS:'):
                    try:
                        params_str = line.split(':', 1)[1].strip()
                        decision_data['parameters'] = json.loads(params_str)
                    except:
                        decision_data['parameters'] = {}
            
            if all(key in decision_data for key in ['action', 'target', 'reasoning', 'confidence']):
                return Decision(
                    action=decision_data['action'],
                    target=decision_data['target'],
                    reasoning=decision_data['reasoning'],
                    confidence=decision_data['confidence'],
                    parameters=decision_data.get('parameters', {}),
                    timestamp=time.time()
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Decision parsing failed: {e}")
            return None
    
    async def _execute_decision(self, decision: Decision):
        """Execute the autonomous decision"""
        try:
            self.logger.info(f"Executing decision: {decision.action} on {decision.target}")
            
            if decision.action == "DISCOVER":
                await self._execute_discovery(decision)
            elif decision.action == "PROFILE":
                await self._execute_profiling(decision)
            elif decision.action == "RESEARCH":
                await self._execute_research(decision)
            elif decision.action == "EXPLOIT":
                await self._execute_exploitation(decision)
            elif decision.action == "ESCALATE":
                await self._execute_escalation(decision)
            elif decision.action == "PERSIST":
                await self._execute_persistence(decision)
            elif decision.action == "PIVOT":
                await self._execute_pivot(decision)
            elif decision.action == "LEARN":
                await self._execute_learning(decision)
            else:
                self.logger.warning(f"Unknown action: {decision.action}")
            
        except Exception as e:
            self.logger.error(f"Decision execution failed: {e}")
    
    async def _execute_discovery(self, decision: Decision):
        """Execute network discovery"""
        try:
            self.state = AgentState.DISCOVERING
            
            # Add manual target if specified
            if decision.target and decision.target != "auto":
                await self.scanner.add_manual_target(decision.target)
            
            self.stats["targets_discovered"] += 1
            
        except Exception as e:
            self.logger.error(f"Discovery execution failed: {e}")
    
    async def _execute_profiling(self, decision: Decision):
        """Execute target profiling"""
        try:
            self.state = AgentState.PROFILING
            
            if decision.target:
                await self.profiler.profile_target(decision.target)
                self.stats["targets_profiled"] += 1
            
        except Exception as e:
            self.logger.error(f"Profiling execution failed: {e}")
    
    async def _execute_research(self, decision: Decision):
        """Execute vulnerability research"""
        try:
            self.state = AgentState.RESEARCHING
            
            if decision.target:
                # Get target info
                target = await self.db.get_target(decision.target)
                if target:
                    target_info = {
                        "ip": target.ip,
                        "hostname": target.hostname,
                        "os": target.os,
                        "services": target.services,
                        "vulnerabilities": target.vulnerabilities
                    }
                    
                    # Research vulnerabilities
                    research_results = await web_researcher.research_target(target_info)
                    
                    # Search for exploits
                    exploit_results = await exploit_searcher.search_related_exploits(target_info)
                    
                    # Update context
                    self.context["available_exploits"].extend([e.__dict__ for e in exploit_results])
            
        except Exception as e:
            self.logger.error(f"Research execution failed: {e}")
    
    async def _execute_exploitation(self, decision: Decision):
        """Execute exploitation attempt"""
        try:
            self.state = AgentState.EXPLOITING
            
            target = decision.target
            exploit_name = decision.parameters.get("exploit", "auto")
            
            # Get target info
            target_obj = await self.db.get_target(target)
            if not target_obj:
                self.logger.warning(f"Target {target} not found")
                return
            
            self.stats["exploits_attempted"] += 1
            
            # Try existing exploits first
            success = await self._try_existing_exploits(target_obj, exploit_name)
            
            if not success:
                # Generate custom exploit
                success = await self._generate_and_try_custom_exploit(target_obj)
            
            if success:
                self.stats["exploits_successful"] += 1
                self.stats["sessions_established"] += 1
            
        except Exception as e:
            self.logger.error(f"Exploitation execution failed: {e}")
    
    async def _try_existing_exploits(self, target: Target, exploit_name: str) -> bool:
        """Try existing exploits against target"""
        try:
            # Get available exploits for target
            target_exploits = await self._get_exploits_for_target(target)
            
            for exploit_info in target_exploits:
                try:
                    # Execute exploit
                    result = await self._execute_exploit(target, exploit_info)
                    
                    if result.success:
                        self.logger.info(f"Exploit successful: {exploit_info['name']} on {target.ip}")
                        
                        # Store session if established
                        if result.session_id:
                            session = Session(
                                session_id=result.session_id,
                                target=target.ip,
                                exploit_used=exploit_info['name'],
                                payload=result.payload
                            )
                            await self.db.store_session(session)
                            self.active_sessions.append(result.session_id)
                        
                        # Update target status
                        await self.db.update_target_status(target.ip, True, result.session_id)
                        
                        return True
                    
                except Exception as e:
                    self.logger.error(f"Exploit {exploit_info['name']} failed: {e}")
                    continue
            
            return False
            
        except Exception as e:
            self.logger.error(f"Existing exploits failed: {e}")
            return False
    
    async def _generate_and_try_custom_exploit(self, target: Target) -> bool:
        """Generate and try custom exploit"""
        try:
            # Prepare target info
            target_info = {
                "ip": target.ip,
                "hostname": target.hostname,
                "os": target.os,
                "services": target.services,
                "vulnerabilities": target.vulnerabilities
            }
            
            # Find vulnerability to exploit
            vulnerability = await self._select_vulnerability_for_exploit(target)
            if not vulnerability:
                return False
            
            # Generate custom exploit
            exploit = await self.exploit_generator.generate_exploit(target_info, vulnerability)
            if not exploit:
                return False
            
            # Execute generated exploit
            result = await self._execute_generated_exploit(target, exploit)
            
            return result.success
            
        except Exception as e:
            self.logger.error(f"Custom exploit generation failed: {e}")
            return False
    
    async def _execute_exploit(self, target: Target, exploit_info: Dict[str, Any]) -> Any:
        """Execute exploit against target"""
        try:
            # Use exploit_tools to execute
            if exploit_info['source'] == 'metasploit':
                # Execute Metasploit exploit
                payload_config = self._create_payload_config(target)
                result = exploit_tools.execute_metasploit_exploit(
                    exploit_info['name'],
                    target.ip,
                    payload_config
                )
                return result
            else:
                # Execute custom exploit
                result = exploit_tools.execute_custom_exploit(
                    exploit_info['path'],
                    target.ip
                )
                return result
            
        except Exception as e:
            self.logger.error(f"Exploit execution failed: {e}")
            return None
    
    async def _execute_generated_exploit(self, target: Target, exploit: Any) -> Any:
        """Execute generated exploit"""
        try:
            # Save exploit to temporary file
            temp_path = f"/tmp/generated_exploit_{int(time.time())}.py"
            with open(temp_path, 'w') as f:
                f.write(exploit.code)
            
            # Execute exploit
            result = exploit_tools.execute_custom_exploit(temp_path, target.ip)
            
            # Cleanup
            import os
            try:
                os.remove(temp_path)
            except:
                pass
            
            return result
            
        except Exception as e:
            self.logger.error(f"Generated exploit execution failed: {e}")
            return None
    
    def _create_payload_config(self, target: Target) -> Any:
        """Create payload configuration"""
        from .exploit_dev.generator import PayloadConfig
        
        return PayloadConfig(
            payload_type="reverse_tcp",
            target_platform=target.os or "linux",
            target_arch="x86",
            lhost="127.0.0.1",  # Would be configured properly
            lport=4444
        )
    
    async def _select_vulnerability_for_exploit(self, target: Target) -> Optional[Dict[str, Any]]:
        """Select vulnerability for exploit generation"""
        try:
            if not target.vulnerabilities:
                return None
            
            # Select highest severity vulnerability
            vulnerabilities = sorted(
                target.vulnerabilities,
                key=lambda v: self._get_severity_score(v.get('severity', 'unknown')),
                reverse=True
            )
            
            return vulnerabilities[0] if vulnerabilities else None
            
        except Exception as e:
            self.logger.error(f"Vulnerability selection failed: {e}")
            return None
    
    def _get_severity_score(self, severity: str) -> int:
        """Get severity score for sorting"""
        severity_map = {
            "critical": 4,
            "high": 3,
            "medium": 2,
            "low": 1,
            "unknown": 0
        }
        return severity_map.get(severity.lower(), 0)
    
    async def _execute_escalation(self, decision: Decision):
        """Execute privilege escalation"""
        try:
            session_id = decision.parameters.get("session_id")
            if not session_id:
                # Find active session for target
                session_id = await self._find_session_for_target(decision.target)
            
            if session_id:
                # Get target OS
                target = await self.db.get_target(decision.target)
                target_os = target.os if target else "linux"
                
                # Perform privilege escalation
                escalation_results = exploit_tools.privilege_escalation(session_id, target_os)
                
                # Log escalation attempt
                self.action_logger.log_privilege_escalation(
                    session_id,
                    decision.target,
                    len(escalation_results) > 0
                )
            
        except Exception as e:
            self.logger.error(f"Escalation execution failed: {e}")
    
    async def _execute_persistence(self, decision: Decision):
        """Execute persistence establishment"""
        try:
            session_id = decision.parameters.get("session_id")
            if not session_id:
                session_id = await self._find_session_for_target(decision.target)
            
            if session_id:
                # Get target OS
                target = await self.db.get_target(decision.target)
                target_os = target.os if target else "linux"
                
                # Establish persistence
                success = exploit_tools.establish_persistence(session_id, target_os)
                
                # Log persistence attempt
                self.action_logger.log_persistence(
                    session_id,
                    decision.target,
                    success
                )
            
        except Exception as e:
            self.logger.error(f"Persistence execution failed: {e}")
    
    async def _execute_pivot(self, decision: Decision):
        """Execute pivot to new target"""
        try:
            # Find new targets to pivot to
            new_targets = await self._find_pivot_targets()
            
            for target in new_targets:
                # Schedule profiling and exploitation
                await self.profiler.profile_target(target.ip)
            
        except Exception as e:
            self.logger.error(f"Pivot execution failed: {e}")
    
    async def _execute_learning(self, decision: Decision):
        """Execute learning from recent attempts"""
        try:
            self.state = AgentState.LEARNING
            
            # Analyze recent experiences
            recent_experiences = await self.db.get_experiences(limit=100)
            
            # Extract patterns
            patterns = self._extract_patterns(recent_experiences)
            
            # Update learned patterns
            self.context["learned_patterns"].update(patterns)
            
        except Exception as e:
            self.logger.error(f"Learning execution failed: {e}")
    
    async def _learn_from_decision(self, decision: Decision):
        """Learn from decision outcome"""
        try:
            # Store experience
            experience = Experience(
                target=decision.target,
                action=decision.action,
                tool_used="autonomous_agent",
                success=decision.confidence > 0.7,  # Simple success metric
                timestamp=decision.timestamp,
                context={"decision": decision.__dict__},
                result={"confidence": decision.confidence}
            )
            
            await self.db.store_experience(experience)
            
        except Exception as e:
            self.logger.error(f"Learning from decision failed: {e}")
    
    async def _get_available_exploits(self) -> List[Dict[str, Any]]:
        """Get available exploits"""
        try:
            # Get exploits from database
            exploits = await self.db.get_best_exploits(limit=50)
            return [e.__dict__ for e in exploits]
        except Exception as e:
            self.logger.error(f"Failed to get available exploits: {e}")
            return []
    
    async def _get_exploits_for_target(self, target: Target) -> List[Dict[str, Any]]:
        """Get exploits suitable for target"""
        try:
            # Search for exploits based on target info
            target_info = {
                "ip": target.ip,
                "os": target.os,
                "services": target.services
            }
            
            exploit_results = await exploit_searcher.search_related_exploits(target_info)
            return [e.__dict__ for e in exploit_results]
            
        except Exception as e:
            self.logger.error(f"Failed to get exploits for target: {e}")
            return []
    
    async def _find_session_for_target(self, target_ip: str) -> Optional[str]:
        """Find active session for target"""
        try:
            sessions = await self.db.get_active_sessions()
            for session in sessions:
                if session.target == target_ip:
                    return session.session_id
            return None
        except Exception as e:
            self.logger.error(f"Failed to find session for target: {e}")
            return None
    
    async def _find_pivot_targets(self) -> List[Target]:
        """Find targets to pivot to"""
        try:
            # Get targets that haven't been compromised yet
            all_targets = await self.db.get_all_targets()
            uncompromised = [t for t in all_targets if not t.compromised]
            
            # Prioritize by number of services
            uncompromised.sort(key=lambda t: len(t.services), reverse=True)
            
            return uncompromised[:5]  # Return top 5
            
        except Exception as e:
            self.logger.error(f"Failed to find pivot targets: {e}")
            return []
    
    def _extract_patterns(self, experiences: List[Experience]) -> Dict[str, Any]:
        """Extract patterns from experiences"""
        try:
            patterns = {}
            
            # Group experiences by action
            action_groups = {}
            for exp in experiences:
                if exp.action not in action_groups:
                    action_groups[exp.action] = []
                action_groups[exp.action].append(exp)
            
            # Calculate success rates
            for action, exps in action_groups.items():
                if exps:
                    success_count = sum(1 for exp in exps if exp.success)
                    success_rate = success_count / len(exps)
                    
                    patterns[action] = {
                        "success_rate": success_rate,
                        "usage_count": len(exps),
                        "last_used": max(exp.timestamp for exp in exps)
                    }
            
            return patterns
            
        except Exception as e:
            self.logger.error(f"Pattern extraction failed: {e}")
            return {}
    
    async def _load_learned_patterns(self):
        """Load learned patterns from database"""
        try:
            # Get patterns from database
            patterns = await self.db.get_pattern("learned_patterns")
            if patterns:
                self.context["learned_patterns"] = patterns
            
        except Exception as e:
            self.logger.error(f"Failed to load learned patterns: {e}")
    
    async def _save_learned_patterns(self):
        """Save learned patterns to database"""
        try:
            await self.db.store_pattern("learned_patterns", self.context["learned_patterns"])
        except Exception as e:
            self.logger.error(f"Failed to save learned patterns: {e}")
    
    async def _update_learned_patterns(self):
        """Update learned patterns"""
        try:
            # Get recent experiences
            recent_experiences = await self.db.get_experiences(limit=50)
            
            # Extract new patterns
            new_patterns = self._extract_patterns(recent_experiences)
            
            # Merge with existing patterns
            for pattern_name, pattern_data in new_patterns.items():
                if pattern_name in self.context["learned_patterns"]:
                    # Update existing pattern
                    existing = self.context["learned_patterns"][pattern_name]
                    existing["success_rate"] = pattern_data["success_rate"]
                    existing["usage_count"] = pattern_data["usage_count"]
                    existing["last_used"] = pattern_data["last_used"]
                else:
                    # Add new pattern
                    self.context["learned_patterns"][pattern_name] = pattern_data
            
        except Exception as e:
            self.logger.error(f"Failed to update learned patterns: {e}")
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get current agent status"""
        return {
            "state": self.state.value,
            "running": self.running,
            "statistics": self.stats.copy(),
            "active_sessions": len(self.active_sessions),
            "context_size": {
                "targets": len(self.context["current_targets"]),
                "exploits": len(self.context["available_exploits"]),
                "patterns": len(self.context["learned_patterns"])
            },
            "decision_history_size": len(self.decision_history)
        }


# Global agent instance
agent_instance = None


async def get_agent(config: ConfigManager) -> AutonomousAgent:
    """Get or create agent instance"""
    global agent_instance
    
    if agent_instance is None:
        agent_instance = AutonomousAgent(config)
        await agent_instance.initialize()
    
    return agent_instance
