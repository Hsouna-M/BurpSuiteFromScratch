"""
Redis Storage Module
Handles storing and retrieving intercepted requests from Redis database
"""

import json
import redis
from typing import Optional, List, Dict, Any


class RedisStorage:
    """Manages Redis connection and operations for intercepted requests"""
    
    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0):
        """
        Initialize Redis connection
        
        Args:
            host: Redis server host
            port: Redis server port
            db: Redis database number
        """
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True
        )
        
        # Test connection
        try:
            self.client.ping()
            print(f"[+] Connected to Redis at {host}:{port}")
        except redis.ConnectionError as e:
            print(f"[-] Failed to connect to Redis: {e}")
            raise
    
    def save_request(
        self,
        request_id: str,
        hostname: str,
        method: str,
        path: str,
        headers: Dict[str, str],
        body: str,
        timestamp: str
    ) -> bool:
        """
        Save intercepted request to Redis
        
        Args:
            request_id: Unique request identifier
            hostname: Target hostname
            method: HTTP method (GET, POST, etc.)
            path: Request path
            headers: Request headers dictionary
            body: Request body (hex encoded for binary safety)
            timestamp: Request timestamp (ISO format)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            request_data = {
                'id': request_id,
                'hostname': hostname,
                'method': method,
                'path': path,
                'headers': json.dumps(headers),
                'body': body,
                'timestamp': timestamp,
            }
            
            # Store request as hash
            self.client.hset(f"request:{request_id}", mapping=request_data)
            
            # Add to pending list for quick access
            self.client.lpush("pending_requests", request_id)
            
            # Set expiration (1 hour)
            self.client.expire(f"request:{request_id}", 3600)
            
            # Set initial status
            self.client.hset(f"request:{request_id}", "status", "pending")
            
            return True
        except Exception as e:
            print(f"[-] Error saving request to Redis: {e}")
            return False
    
    def get_pending_requests(self) -> List[str]:
        """
        Get all pending request IDs
        
        Returns:
            List of request IDs
        """
        try:
            pending_ids = self.client.lrange("pending_requests", 0, -1)
            return pending_ids
        except Exception as e:
            print(f"[-] Error fetching pending requests: {e}")
            return []
    
    def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full request details by ID
        
        Args:
            request_id: The request ID to retrieve
            
        Returns:
            Dictionary with request data or None if not found
        """
        try:
            request_data = self.client.hgetall(f"request:{request_id}")
            
            if not request_data:
                return None
            
            # Parse headers back from JSON
            try:
                request_data['headers'] = json.loads(request_data['headers'])
            except json.JSONDecodeError:
                request_data['headers'] = {}
            
            return request_data
        except Exception as e:
            print(f"[-] Error retrieving request: {e}")
            return None
    
    
    def update_request_status(self, request_id: str, status: str) -> bool:
        """
        Update request status (pending, allowed, blocked, modified)
        
        Args:
            request_id: The request ID
            status: New status
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.hset(f"request:{request_id}", "status", status)
            return True
        except Exception as e:
            print(f"[-] Error updating status: {e}")
            return False

    def get_request_status(self, request_id: str) -> str:
        """
        Get current request status
        
        Args:
            request_id: The request ID
            
        Returns:
            Status string or 'unknown'
        """
        try:
            status = self.client.hget(f"request:{request_id}", "status")
            return status if status else 'unknown'
        except Exception as e:
            print(f"[-] Error getting status: {e}")
            return 'error'

    def save_response(self, request_id: str, status_code: int, headers: Dict[str, str], body: str) -> bool:
        """
        Save response for a request
        
        Args:
            request_id: The request ID
            status_code: Response status code
            headers: Response headers
            body: Response body (hex encoded or string)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response_data = {
                'status_code': status_code,
                'headers': json.dumps(headers),
                'body': body,
                'status': 'pending'  # Initial status for response interception
            }
            self.client.hset(f"response:{request_id}", mapping=response_data)
            self.client.expire(f"response:{request_id}", 3600)
            return True
        except Exception as e:
            print(f"[-] Error saving response: {e}")
            return False
            
    def get_response(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get response for a request
        
        Args:
            request_id: The request ID
            
        Returns:
            Dictionary with response data or None
        """
        try:
            response_data = self.client.hgetall(f"response:{request_id}")
            if not response_data:
                return None
                
            try:
                response_data['headers'] = json.loads(response_data['headers'])
            except:
                response_data['headers'] = {}
                
            return response_data
        except Exception as e:
            print(f"[-] Error getting response: {e}")
            return None

    def update_response_status(self, request_id: str, status: str) -> bool:
        """
        Update response status (pending, allowed, blocked, modified)
        
        Args:
            request_id: The request ID
            status: New status
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.hset(f"response:{request_id}", "status", status)
            return True
        except Exception as e:
            print(f"[-] Error updating response status: {e}")
            return False

    def get_response_status(self, request_id: str) -> str:
        """
        Get current response status
        
        Args:
            request_id: The request ID
            
        Returns:
            Status string or 'unknown'
        """
        try:
            status = self.client.hget(f"response:{request_id}", "status")
            return status if status else 'unknown'
        except Exception as e:
            print(f"[-] Error getting response status: {e}")
            return 'error'

    def update_request_data(self, request_id: str, headers: Optional[Dict] = None, body: Optional[str] = None) -> bool:
        """
        Update request headers and body
        
        Args:
            request_id: The request ID
            headers: New headers (optional)
            body: New body (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            updates = {}
            if headers is not None:
                updates['headers'] = json.dumps(headers)
            if body is not None:
                updates['body'] = body
                
            if updates:
                self.client.hset(f"request:{request_id}", mapping=updates)
            return True
        except Exception as e:
            print(f"[-] Error updating request data: {e}")
            return False

    def update_response_data(self, request_id: str, headers: Optional[Dict] = None, body: Optional[str] = None) -> bool:
        """
        Update response headers and body
        
        Args:
            request_id: The request ID
            headers: New headers (optional)
            body: New body (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            updates = {}
            if headers is not None:
                updates['headers'] = json.dumps(headers)
            if body is not None:
                updates['body'] = body
                
            if updates:
                self.client.hset(f"response:{request_id}", mapping=updates)
            return True
        except Exception as e:
            print(f"[-] Error updating response data: {e}")
            return False

    def set_modified_body(self, request_id: str, modified_body: str) -> bool:
        """
        Save modified request body
        
        Args:
            request_id: The request ID
            modified_body: The modified request body
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.hset(f"request:{request_id}", "modified_body", modified_body)
            return True
        except Exception as e:
            print(f"[-] Error saving modified body: {e}")
            return False
    
    def get_modified_body(self, request_id: str) -> Optional[str]:
        """
        Get modified request body
        
        Args:
            request_id: The request ID
            
        Returns:
            Modified body or None if not found
        """
        try:
            modified_body = self.client.hget(f"request:{request_id}", "modified_body")
            return modified_body
        except Exception as e:
            print(f"[-] Error retrieving modified body: {e}")
            return None
    
    def delete_request(self, request_id: str) -> bool:
        """
        Delete request from Redis
        
        Args:
            request_id: The request ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.delete(f"request:{request_id}")
            self.client.lrem("pending_requests", 0, request_id)
            return True
        except Exception as e:
            print(f"[-] Error deleting request: {e}")
            return False
    
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get Redis health status
        
        Returns:
            Dictionary with health information
        """
        try:
            self.client.ping()
            info = self.client.info()
            return {
                'status': 'connected',
                'redis_version': info.get('redis_version', 'unknown'),
                'connected_clients': info.get('connected_clients', 0)
            }
        except Exception as e:
            return {
                'status': 'disconnected',
                'error': str(e)
            }

    def flush_all_instances(self) : 
        self.client.flushdb()


   ### i do not think i need this ( junk ) 

    def clear_all_requests(self) -> bool:
        """
        Clear all requests from Redis (use with caution)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get all pending request IDs
            pending_ids = self.client.lrange("pending_requests", 0, -1)
            
            # Delete each request
            for req_id in pending_ids:
                self.client.delete(f"request:{req_id}")
            
            # Clear pending list
            self.client.delete("pending_requests")
            return True
        except Exception as e:
            print(f"[-] Error clearing requests: {e}")
            return False

    # -------------------------------------------------------------------------
    # Proxy Configuration Methods (Filter Mode)
    # -------------------------------------------------------------------------

    def set_proxy_mode(self, mode: str) -> bool:
        """
        Set proxy operation mode ('intercept' or 'filter')
        
        Args:
            mode: The mode string
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if mode not in ['intercept', 'filter']:
                return False
            self.client.set("proxy_config:mode", mode)
            return True
        except Exception as e:
            print(f"[-] Error setting proxy mode: {e}")
            return False

    def get_proxy_mode(self) -> str:
        """
        Get current proxy operation mode
        
        Returns:
            Mode string ('intercept' or 'filter') - defaults to 'intercept'
        """
        try:
            mode = self.client.get("proxy_config:mode")
            return mode if mode else "intercept"
        except Exception as e:
            print(f"[-] Error getting proxy mode: {e}")
            return "intercept"

    def add_blocked_domain(self, domain: str) -> bool:
        """Add domain to blocklist"""
        try:
            self.client.sadd("proxy_config:blocked_domains", domain)
            return True
        except Exception as e:
            print(f"[-] Error adding blocked domain: {e}")
            return False

    def remove_blocked_domain(self, domain: str) -> bool:
        """Remove domain from blocklist"""
        try:
            self.client.srem("proxy_config:blocked_domains", domain)
            return True
        except Exception as e:
            print(f"[-] Error removing blocked domain: {e}")
            return False

    def get_blocked_domains(self) -> List[str]:
        """Get list of blocked domains"""
        try:
            return list(self.client.smembers("proxy_config:blocked_domains"))
        except Exception as e:
            print(f"[-] Error getting blocked domains: {e}")
            return []

    def add_blocked_keyword(self, keyword: str) -> bool:
        """Add keyword to blocklist"""
        try:
            self.client.sadd("proxy_config:blocked_keywords", keyword)
            return True
        except Exception as e:
            print(f"[-] Error adding blocked keyword: {e}")
            return False

    def remove_blocked_keyword(self, keyword: str) -> bool:
        """Remove keyword from blocklist"""
        try:
            self.client.srem("proxy_config:blocked_keywords", keyword)
            return True
        except Exception as e:
            print(f"[-] Error removing blocked keyword: {e}")
            return False

    def get_blocked_keywords(self) -> List[str]:
        """Get list of blocked keywords"""
        try:
            return list(self.client.smembers("proxy_config:blocked_keywords"))
        except Exception as e:
            print(f"[-] Error getting blocked keywords: {e}")
            return []