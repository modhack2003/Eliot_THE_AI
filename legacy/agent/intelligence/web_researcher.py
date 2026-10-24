"""
Web scraping and research capabilities for target intelligence
"""

import requests
import asyncio
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import json


@dataclass
class ResearchResult:
    """Result from web research"""
    source: str
    url: str
    title: str
    content: str
    relevance_score: float
    keywords_found: List[str]
    timestamp: float


@dataclass
class CredentialResult:
    """Default credentials found"""
    service: str
    username: str
    password: str
    source: str
    verified: bool = False


@dataclass
class TechnologyInfo:
    """Information about a technology"""
    name: str
    version: str
    vulnerabilities: List[str]
    default_credentials: List[CredentialResult]
    documentation_urls: List[str]


class WebResearcher:
    """Web research capabilities for intelligence gathering"""
    
    def __init__(self):
        self.logger = logging.getLogger("web_researcher")
        self.executor = ThreadPoolExecutor(max_workers=5)
        
        # Research sources
        self.sources = {
            "default_creds": [
                "https://github.com/danielmiessler/SecLists/tree/master/Passwords/Default-Credentials",
                "https://cirt.net/passwords",
                "https://datarecovery.com/rd/default-passwords/",
                "https://www.routerpasswords.com/",
                "https://www.phenoelit.org/dpl/dpl.html"
            ],
            "exploit_info": [
                "https://www.exploit-db.com/",
                "https://github.com/",
                "https://packetstormsecurity.com/",
                "https://0day.today/",
                "https://www.rapid7.com/db/",
                "https://www.tenable.com/plugins"
            ],
            "tech_docs": [
                "https://docs.microsoft.com/",
                "https://docs.oracle.com/",
                "https://docs.aws.amazon.com/",
                "https://docs.docker.com/",
                "https://docs.nginx.com/"
            ]
        }
        
        # User agents for web scraping
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]
    
    async def research_target(self, target_info: Dict[str, Any]) -> List[ResearchResult]:
        """Research target information from web sources"""
        self.logger.info(f"Researching target: {target_info.get('ip', 'unknown')}")
        
        all_results = []
        
        # Research different aspects
        research_tasks = [
            self._research_default_credentials(target_info),
            self._research_vulnerabilities(target_info),
            self._research_technologies(target_info),
            self._research_osint(target_info)
        ]
        
        results = await asyncio.gather(*research_tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, list):
                all_results.extend(result)
            elif isinstance(result, Exception):
                self.logger.error(f"Research error: {result}")
        
        # Sort by relevance score
        all_results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return all_results
    
    async def _research_default_credentials(self, target_info: Dict[str, Any]) -> List[ResearchResult]:
        """Research default credentials for target services"""
        try:
            results = []
            services = target_info.get("services", [])
            
            for service in services:
                if isinstance(service, dict):
                    service_name = service.get("service", "")
                    service_version = service.get("version", "")
                    
                    # Search for default credentials
                    search_queries = [
                        f"{service_name} default password",
                        f"{service_name} {service_version} default credentials",
                        f"{service_name} admin password",
                        f"{service_name} default login"
                    ]
                    
                    for query in search_queries:
                        search_results = await self._search_web(query, max_results=5)
                        results.extend(search_results)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Default credentials research failed: {e}")
            return []
    
    async def _research_vulnerabilities(self, target_info: Dict[str, Any]) -> List[ResearchResult]:
        """Research vulnerabilities for target"""
        try:
            results = []
            
            # Research by OS
            if "os" in target_info:
                os_results = await self._search_web(f"{target_info['os']} vulnerabilities", max_results=10)
                results.extend(os_results)
            
            # Research by services
            services = target_info.get("services", [])
            for service in services:
                if isinstance(service, dict):
                    service_name = service.get("service", "")
                    service_version = service.get("version", "")
                    
                    vuln_queries = [
                        f"{service_name} vulnerabilities",
                        f"{service_name} {service_version} exploit",
                        f"{service_name} CVE",
                        f"{service_name} security issues"
                    ]
                    
                    for query in vuln_queries:
                        search_results = await self._search_web(query, max_results=5)
                        results.extend(search_results)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Vulnerability research failed: {e}")
            return []
    
    async def _research_technologies(self, target_info: Dict[str, Any]) -> List[ResearchResult]:
        """Research technologies used by target"""
        try:
            results = []
            
            # Research web technologies
            if "web_technologies" in target_info:
                for tech, version in target_info["web_technologies"].items():
                    tech_results = await self._search_web(f"{tech} {version} security", max_results=5)
                    results.extend(tech_results)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Technology research failed: {e}")
            return []
    
    async def _research_osint(self, target_info: Dict[str, Any]) -> List[ResearchResult]:
        """Research OSINT information about target"""
        try:
            results = []
            
            # Research by IP/hostname
            ip = target_info.get("ip", "")
            hostname = target_info.get("hostname", "")
            
            if ip:
                osint_queries = [
                    f"site:{ip}",
                    f"{ip} security",
                    f"{ip} vulnerability",
                    f"{ip} exploit"
                ]
                
                for query in osint_queries:
                    search_results = await self._search_web(query, max_results=3)
                    results.extend(search_results)
            
            if hostname:
                hostname_queries = [
                    f"{hostname} security",
                    f"{hostname} vulnerability",
                    f"{hostname} exploit"
                ]
                
                for query in hostname_queries:
                    search_results = await self._search_web(query, max_results=3)
                    results.extend(search_results)
            
            return results
            
        except Exception as e:
            self.logger.error(f"OSINT research failed: {e}")
            return []
    
    async def _search_web(self, query: str, max_results: int = 10) -> List[ResearchResult]:
        """Search the web for information"""
        try:
            # Use DuckDuckGo for web search (no API key required)
            search_url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
            
            headers = {
                "User-Agent": self.user_agents[0],
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive"
            }
            
            response = requests.get(search_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parse search results
            results = self._parse_search_results(response.text, query)
            
            return results[:max_results]
            
        except Exception as e:
            self.logger.error(f"Web search failed for '{query}': {e}")
            return []
    
    def _parse_search_results(self, html_content: str, query: str) -> List[ResearchResult]:
        """Parse search results from HTML"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            results = []
            
            # Find result links (this is specific to DuckDuckGo)
            result_links = soup.find_all('a', class_='result__a')
            
            for link in result_links:
                try:
                    title = link.get_text().strip()
                    url = link.get('href', '')
                    
                    if url and title:
                        # Calculate relevance score
                        relevance_score = self._calculate_relevance(title, query)
                        
                        result = ResearchResult(
                            source="web_search",
                            url=url,
                            title=title,
                            content=title,  # Simplified - would need to fetch full content
                            relevance_score=relevance_score,
                            keywords_found=self._extract_keywords(title, query),
                            timestamp=time.time()
                        )
                        results.append(result)
                
                except Exception as e:
                    self.logger.debug(f"Error parsing search result: {e}")
                    continue
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to parse search results: {e}")
            return []
    
    def _calculate_relevance(self, text: str, query: str) -> float:
        """Calculate relevance score for search result"""
        try:
            text_lower = text.lower()
            query_lower = query.lower()
            query_words = query_lower.split()
            
            score = 0.0
            
            # Exact phrase match
            if query_lower in text_lower:
                score += 10.0
            
            # Word matches
            for word in query_words:
                if word in text_lower:
                    score += 1.0
            
            # Bonus for security-related terms
            security_terms = ["exploit", "vulnerability", "cve", "security", "hack", "password", "credential"]
            for term in security_terms:
                if term in text_lower:
                    score += 0.5
            
            return min(score, 10.0)  # Cap at 10
            
        except Exception as e:
            self.logger.error(f"Relevance calculation failed: {e}")
            return 0.0
    
    def _extract_keywords(self, text: str, query: str) -> List[str]:
        """Extract relevant keywords from text"""
        try:
            keywords = []
            text_lower = text.lower()
            query_lower = query.lower()
            
            # Extract query words
            query_words = query_lower.split()
            for word in query_words:
                if word in text_lower and len(word) > 2:
                    keywords.append(word)
            
            # Extract security-related keywords
            security_terms = ["exploit", "vulnerability", "cve", "security", "hack", "password", "credential", "default"]
            for term in security_terms:
                if term in text_lower:
                    keywords.append(term)
            
            return list(set(keywords))  # Remove duplicates
            
        except Exception as e:
            self.logger.error(f"Keyword extraction failed: {e}")
            return []
    
    async def scrape_default_credentials(self, service: str) -> List[CredentialResult]:
        """Scrape default credentials for a service"""
        try:
            credentials = []
            
            # Search for default credentials
            search_results = await self._search_web(f"{service} default password credentials", max_results=5)
            
            for result in search_results:
                # Fetch full content
                content = await self._fetch_page_content(result.url)
                
                if content:
                    # Parse credentials from content
                    found_creds = self._parse_credentials(content, service)
                    credentials.extend(found_creds)
            
            return credentials
            
        except Exception as e:
            self.logger.error(f"Default credentials scraping failed for {service}: {e}")
            return []
    
    async def _fetch_page_content(self, url: str) -> Optional[str]:
        """Fetch page content"""
        try:
            headers = {
                "User-Agent": self.user_agents[0]
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parse HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text
            
        except Exception as e:
            self.logger.error(f"Failed to fetch content from {url}: {e}")
            return None
    
    def _parse_credentials(self, content: str, service: str) -> List[CredentialResult]:
        """Parse credentials from content"""
        try:
            credentials = []
            content_lower = content.lower()
            service_lower = service.lower()
            
            # Look for credential patterns
            patterns = [
                r'username[:\s]+([^\s\n]+)',
                r'user[:\s]+([^\s\n]+)',
                r'login[:\s]+([^\s\n]+)',
                r'admin[:\s]+([^\s\n]+)',
                r'password[:\s]+([^\s\n]+)',
                r'pass[:\s]+([^\s\n]+)',
                r'pwd[:\s]+([^\s\n]+)'
            ]
            
            # Simple credential extraction (would need more sophisticated parsing)
            lines = content.split('\n')
            for i, line in enumerate(lines):
                line_lower = line.lower()
                if service_lower in line_lower or 'default' in line_lower:
                    # Look for credentials in nearby lines
                    for j in range(max(0, i-2), min(len(lines), i+3)):
                        nearby_line = lines[j].lower()
                        if 'username' in nearby_line or 'password' in nearby_line:
                            # Extract credentials (simplified)
                            username = self._extract_credential(lines[j], 'username')
                            password = self._extract_credential(lines[j], 'password')
                            
                            if username and password:
                                cred = CredentialResult(
                                    service=service,
                                    username=username,
                                    password=password,
                                    source="web_scraping"
                                )
                                credentials.append(cred)
            
            return credentials
            
        except Exception as e:
            self.logger.error(f"Credential parsing failed: {e}")
            return []
    
    def _extract_credential(self, text: str, cred_type: str) -> Optional[str]:
        """Extract credential value from text"""
        try:
            patterns = {
                'username': [r'username[:\s]+([^\s\n]+)', r'user[:\s]+([^\s\n]+)', r'login[:\s]+([^\s\n]+)'],
                'password': [r'password[:\s]+([^\s\n]+)', r'pass[:\s]+([^\s\n]+)', r'pwd[:\s]+([^\s\n]+)']
            }
            
            if cred_type in patterns:
                for pattern in patterns[cred_type]:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        return match.group(1).strip()
            
            return None
            
        except Exception as e:
            self.logger.error(f"Credential extraction failed: {e}")
            return None
    
    async def get_technology_info(self, technology: str, version: str = None) -> Optional[TechnologyInfo]:
        """Get information about a technology"""
        try:
            # Search for technology information
            query = f"{technology} {version}" if version else technology
            search_results = await self._search_web(f"{query} security vulnerabilities", max_results=5)
            
            vulnerabilities = []
            default_credentials = []
            documentation_urls = []
            
            for result in search_results:
                # Extract vulnerabilities
                if 'vulnerability' in result.content.lower() or 'cve' in result.content.lower():
                    vulnerabilities.append(result.title)
                
                # Extract documentation URLs
                if 'docs' in result.url or 'documentation' in result.url:
                    documentation_urls.append(result.url)
                
                # Get default credentials
                creds = await self.scrape_default_credentials(technology)
                default_credentials.extend(creds)
            
            tech_info = TechnologyInfo(
                name=technology,
                version=version or "unknown",
                vulnerabilities=vulnerabilities,
                default_credentials=default_credentials,
                documentation_urls=documentation_urls
            )
            
            return tech_info
            
        except Exception as e:
            self.logger.error(f"Technology info gathering failed for {technology}: {e}")
            return None
    
    def __del__(self):
        """Cleanup thread pool"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)


# Global instance
web_researcher = WebResearcher()
