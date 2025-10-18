"""
MongoDB-based experience database for storing exploitation attempts and outcomes
"""

import pymongo
import json
import time
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from bson import ObjectId
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient


@dataclass
class Experience:
    """Represents an exploitation experience"""
    target: str
    action: str
    tool_used: str
    success: bool
    timestamp: float
    context: Dict[str, Any]
    result: Dict[str, Any]
    error: Optional[str] = None
    session_id: Optional[str] = None
    exploit_name: Optional[str] = None
    payload: Optional[str] = None


@dataclass
class Target:
    """Represents a target system"""
    ip: str
    hostname: Optional[str] = None
    os: Optional[str] = None
    services: List[Dict[str, Any]] = None
    vulnerabilities: List[Dict[str, Any]] = None
    compromised: bool = False
    sessions: List[str] = None
    last_seen: float = None
    priority: int = 1
    
    def __post_init__(self):
        if self.services is None:
            self.services = []
        if self.vulnerabilities is None:
            self.vulnerabilities = []
        if self.sessions is None:
            self.sessions = []
        if self.last_seen is None:
            self.last_seen = time.time()


@dataclass
class Exploit:
    """Represents an exploit"""
    name: str
    cve: Optional[str] = None
    description: Optional[str] = None
    platform: Optional[str] = None
    arch: Optional[str] = None
    rank: str = "normal"
    success_rate: float = 0.0
    usage_count: int = 0
    last_used: Optional[float] = None
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class Session:
    """Represents a compromised session"""
    session_id: str
    target: str
    exploit_used: str
    payload: Optional[str] = None
    timestamp: float = None
    active: bool = True
    privilege_level: str = "user"
    commands_executed: List[str] = None
    files_accessed: List[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.commands_executed is None:
            self.commands_executed = []
        if self.files_accessed is None:
            self.files_accessed = []


class ExperienceDatabase:
    """MongoDB-based experience database"""
    
    def __init__(self, connection_string: str, database_name: str = "ai_pentesting_agent"):
        self.connection_string = connection_string
        self.database_name = database_name
        self.client = None
        self.db = None
        self.logger = logging.getLogger("experience_db")
        
        # Collection names
        self.collections = {
            "experiences": "experiences",
            "targets": "targets",
            "exploits": "exploits",
            "sessions": "sessions",
            "patterns": "patterns",
            "strategies": "strategies"
        }
    
    async def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(self.connection_string)
            self.db = self.client[self.database_name]
            
            # Test connection
            await self.client.admin.command('ping')
            self.logger.info(f"Connected to MongoDB: {self.database_name}")
            
            # Create indexes
            await self._create_indexes()
            
        except Exception as e:
            self.logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def _create_indexes(self):
        """Create database indexes for better performance"""
        try:
            # Experiences indexes
            await self.db.experiences.create_index("target")
            await self.db.experiences.create_index("timestamp")
            await self.db.experiences.create_index("success")
            await self.db.experiences.create_index("tool_used")
            
            # Targets indexes
            await self.db.targets.create_index("ip", unique=True)
            await self.db.targets.create_index("compromised")
            await self.db.targets.create_index("priority")
            
            # Exploits indexes
            await self.db.exploits.create_index("name")
            await self.db.exploits.create_index("cve")
            await self.db.exploits.create_index("success_rate")
            
            # Sessions indexes
            await self.db.sessions.create_index("session_id", unique=True)
            await self.db.sessions.create_index("target")
            await self.db.sessions.create_index("active")
            
            self.logger.info("Database indexes created successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to create indexes: {e}")
    
    async def store_experience(self, experience: Experience) -> str:
        """Store an exploitation experience"""
        try:
            experience_dict = asdict(experience)
            result = await self.db.experiences.insert_one(experience_dict)
            self.logger.debug(f"Stored experience: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            self.logger.error(f"Failed to store experience: {e}")
            raise
    
    async def get_experiences(self, filter_dict: Dict[str, Any] = None, 
                            limit: int = 1000, sort_by: str = "timestamp") -> List[Experience]:
        """Retrieve experiences with optional filtering"""
        try:
            if filter_dict is None:
                filter_dict = {}
            
            cursor = self.db.experiences.find(filter_dict).sort(sort_by, -1).limit(limit)
            experiences = []
            
            async for doc in cursor:
                # Remove MongoDB _id field before creating Experience object
                doc.pop('_id', None)
                experiences.append(Experience(**doc))
            
            return experiences
        except Exception as e:
            self.logger.error(f"Failed to retrieve experiences: {e}")
            return []
    
    async def get_successful_experiences(self, target: str = None) -> List[Experience]:
        """Get successful exploitation experiences"""
        filter_dict = {"success": True}
        if target:
            filter_dict["target"] = target
        
        return await self.get_experiences(filter_dict)
    
    async def get_failed_experiences(self, target: str = None) -> List[Experience]:
        """Get failed exploitation experiences"""
        filter_dict = {"success": False}
        if target:
            filter_dict["target"] = target
        
        return await self.get_experiences(filter_dict)
    
    async def store_target(self, target: Target) -> str:
        """Store or update target information"""
        try:
            target_dict = asdict(target)
            target_dict['last_seen'] = time.time()
            
            result = await self.db.targets.replace_one(
                {"ip": target.ip}, 
                target_dict, 
                upsert=True
            )
            
            self.logger.debug(f"Stored target: {target.ip}")
            return target.ip
        except Exception as e:
            self.logger.error(f"Failed to store target: {e}")
            raise
    
    async def get_target(self, ip: str) -> Optional[Target]:
        """Get target by IP address"""
        try:
            doc = await self.db.targets.find_one({"ip": ip})
            if doc:
                doc['_id'] = str(doc['_id'])
                return Target(**doc)
            return None
        except Exception as e:
            self.logger.error(f"Failed to get target: {e}")
            return None
    
    async def get_all_targets(self, compromised_only: bool = False) -> List[Target]:
        """Get all targets"""
        try:
            filter_dict = {}
            if compromised_only:
                filter_dict["compromised"] = True
            
            cursor = self.db.targets.find(filter_dict)
            targets = []
            
            async for doc in cursor:
                doc['_id'] = str(doc['_id'])
                targets.append(Target(**doc))
            
            return targets
        except Exception as e:
            self.logger.error(f"Failed to get targets: {e}")
            return []
    
    async def update_target_status(self, ip: str, compromised: bool, session_id: str = None):
        """Update target compromise status"""
        try:
            update_dict = {"compromised": compromised, "last_seen": time.time()}
            
            if session_id:
                await self.db.targets.update_one(
                    {"ip": ip},
                    {"$addToSet": {"sessions": session_id}}
                )
            
            await self.db.targets.update_one(
                {"ip": ip},
                {"$set": update_dict}
            )
            
            self.logger.debug(f"Updated target status: {ip} - compromised: {compromised}")
        except Exception as e:
            self.logger.error(f"Failed to update target status: {e}")
    
    async def store_exploit(self, exploit: Exploit) -> str:
        """Store or update exploit information"""
        try:
            exploit_dict = asdict(exploit)
            
            result = await self.db.exploits.replace_one(
                {"name": exploit.name}, 
                exploit_dict, 
                upsert=True
            )
            
            self.logger.debug(f"Stored exploit: {exploit.name}")
            return exploit.name
        except Exception as e:
            self.logger.error(f"Failed to store exploit: {e}")
            raise
    
    async def get_exploit(self, name: str) -> Optional[Exploit]:
        """Get exploit by name"""
        try:
            doc = await self.db.exploits.find_one({"name": name})
            if doc:
                doc['_id'] = str(doc['_id'])
                return Exploit(**doc)
            return None
        except Exception as e:
            self.logger.error(f"Failed to get exploit: {e}")
            return None
    
    async def get_best_exploits(self, limit: int = 10) -> List[Exploit]:
        """Get exploits sorted by success rate"""
        try:
            cursor = self.db.exploits.find().sort("success_rate", -1).limit(limit)
            exploits = []
            
            async for doc in cursor:
                doc['_id'] = str(doc['_id'])
                exploits.append(Exploit(**doc))
            
            return exploits
        except Exception as e:
            self.logger.error(f"Failed to get best exploits: {e}")
            return []
    
    async def update_exploit_stats(self, name: str, success: bool):
        """Update exploit success statistics"""
        try:
            # Get current stats
            exploit = await self.get_exploit(name)
            if not exploit:
                return
            
            # Update statistics
            new_usage_count = exploit.usage_count + 1
            if success:
                new_success_rate = (exploit.success_rate * exploit.usage_count + 1) / new_usage_count
            else:
                new_success_rate = (exploit.success_rate * exploit.usage_count) / new_usage_count
            
            await self.db.exploits.update_one(
                {"name": name},
                {
                    "$set": {
                        "success_rate": new_success_rate,
                        "usage_count": new_usage_count,
                        "last_used": time.time()
                    }
                }
            )
            
            self.logger.debug(f"Updated exploit stats: {name} - success_rate: {new_success_rate}")
        except Exception as e:
            self.logger.error(f"Failed to update exploit stats: {e}")
    
    async def store_session(self, session: Session) -> str:
        """Store session information"""
        try:
            session_dict = asdict(session)
            
            result = await self.db.sessions.replace_one(
                {"session_id": session.session_id}, 
                session_dict, 
                upsert=True
            )
            
            self.logger.debug(f"Stored session: {session.session_id}")
            return session.session_id
        except Exception as e:
            self.logger.error(f"Failed to store session: {e}")
            raise
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID"""
        try:
            doc = await self.db.sessions.find_one({"session_id": session_id})
            if doc:
                doc['_id'] = str(doc['_id'])
                return Session(**doc)
            return None
        except Exception as e:
            self.logger.error(f"Failed to get session: {e}")
            return None
    
    async def get_active_sessions(self) -> List[Session]:
        """Get all active sessions"""
        try:
            cursor = self.db.sessions.find({"active": True})
            sessions = []
            
            async for doc in cursor:
                doc['_id'] = str(doc['_id'])
                sessions.append(Session(**doc))
            
            return sessions
        except Exception as e:
            self.logger.error(f"Failed to get active sessions: {e}")
            return []
    
    async def update_session(self, session_id: str, update_dict: Dict[str, Any]):
        """Update session information"""
        try:
            await self.db.sessions.update_one(
                {"session_id": session_id},
                {"$set": update_dict}
            )
            
            self.logger.debug(f"Updated session: {session_id}")
        except Exception as e:
            self.logger.error(f"Failed to update session: {e}")
    
    async def store_pattern(self, pattern_name: str, pattern_data: Dict[str, Any]):
        """Store learned patterns"""
        try:
            pattern_doc = {
                "name": pattern_name,
                "data": pattern_data,
                "timestamp": time.time(),
                "usage_count": 0
            }
            
            result = await self.db.patterns.replace_one(
                {"name": pattern_name}, 
                pattern_doc, 
                upsert=True
            )
            
            self.logger.debug(f"Stored pattern: {pattern_name}")
        except Exception as e:
            self.logger.error(f"Failed to store pattern: {e}")
    
    async def get_pattern(self, pattern_name: str) -> Optional[Dict[str, Any]]:
        """Get learned pattern"""
        try:
            doc = await self.db.patterns.find_one({"name": pattern_name})
            if doc:
                return doc.get("data")
            return None
        except Exception as e:
            self.logger.error(f"Failed to get pattern: {e}")
            return None
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            stats = {
                "total_experiences": await self.db.experiences.count_documents({}),
                "successful_experiences": await self.db.experiences.count_documents({"success": True}),
                "failed_experiences": await self.db.experiences.count_documents({"success": False}),
                "total_targets": await self.db.targets.count_documents({}),
                "compromised_targets": await self.db.targets.count_documents({"compromised": True}),
                "total_exploits": await self.db.exploits.count_documents({}),
                "active_sessions": await self.db.sessions.count_documents({"active": True}),
                "total_sessions": await self.db.sessions.count_documents({}),
                "total_patterns": await self.db.patterns.count_documents({})
            }
            
            return stats
        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}")
            return {}
    
    async def cleanup_old_data(self, days: int = 30):
        """Clean up old data"""
        try:
            cutoff_time = time.time() - (days * 24 * 60 * 60)
            
            # Clean up old experiences
            result = await self.db.experiences.delete_many({"timestamp": {"$lt": cutoff_time}})
            self.logger.info(f"Cleaned up {result.deleted_count} old experiences")
            
            # Clean up inactive sessions
            result = await self.db.sessions.delete_many({
                "active": False,
                "timestamp": {"$lt": cutoff_time}
            })
            self.logger.info(f"Cleaned up {result.deleted_count} old sessions")
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old data: {e}")
    
    async def close(self):
        """Close database connection"""
        if self.client:
            self.client.close()
            self.logger.info("Database connection closed")


# Global database instance
db_instance = None


async def get_database(connection_string: str = None, database_name: str = None) -> ExperienceDatabase:
    """Get or create database instance"""
    global db_instance
    
    if db_instance is None:
        if connection_string is None:
            from ..config_manager import config
            connection_string = config.get_connection_string()
            database_name = config.database.database
        
        db_instance = ExperienceDatabase(connection_string, database_name)
        await db_instance.connect()
    
    return db_instance
