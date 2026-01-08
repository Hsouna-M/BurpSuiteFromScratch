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
                'status': 'pending'
            }
            
            # Store request as hash
            self.client.hset(f"request:{request_id}", mapping=request_data)
            
            # Add to pending list for quick access
            self.client.lpush("pending_requests", request_id)
            
            # Set expiration (1 hour)
            self.client.expire(f"request:{request_id}", 3600)
            
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
    
    def get_request_status(self, request_id: str) -> Optional[str]:
        """
        Get request status
        
        Args:
            request_id: The request ID
            
        Returns:
            Status string (pending, allowed, blocked, modified) or None
        """
        try:
            status = self.client.hget(f"request:{request_id}", "status")
            return status
        except Exception as e:
            print(f"[-] Error getting request status: {e}")
            return None
    
    def update_request_status(self, request_id: str, status: str) -> bool:
        """
        Update request status
        
        Args:
            request_id: The request ID
            status: New status (pending, allowed, blocked, modified)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.hset(f"request:{request_id}", "status", status)
            return True
        except Exception as e:
            print(f"[-] Error updating request status: {e}")
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