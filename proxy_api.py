"""
Proxy API Module
Flask API for GUI communication with the MITM proxy
"""

from flask import Flask, jsonify, request as flask_request
from redis_storage import RedisStorage
from typing import Tuple, Dict, Any


class ProxyAPI:
    """Flask REST API for MITM proxy communication"""
    
    def __init__(self, storage: RedisStorage, port: int = 9000):
        """
        Initialize Proxy API
        
        Args:
            storage: RedisStorage instance
            port: Port to listen on
        """
        self.storage = storage
        self.port = port
        self.app = Flask(__name__)
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Setup all Flask routes"""
        
        # Request endpoints
        @self.app.route('/api/requests', methods=['GET'])
        def get_pending_requests() -> Tuple[Dict[str, Any], int]:
            """Get all pending requests"""
            pending_ids = self.storage.get_pending_requests()
            requests_list = []
            
            for req_id in pending_ids:
                req = self.storage.get_request(req_id)
                requests_list.append({
                    'id': req['id'],
                    'hostname': req['hostname'],
                    'method': req['method'],
                    'path': req['path'],
                    'timestamp': req['timestamp']
                })
            
            return jsonify(requests_list), 200
        
        @self.app.route('/api/requests/<request_id>', methods=['GET'])
        def get_request_details(request_id: str) -> Tuple[Dict[str, Any], int]:
            """Get full request details"""
            req = self.storage.get_request(request_id)
            
            if not req:
                return jsonify({'error': 'Request not found'}), 404
            
            try:
                body_str = req['body']
            except Exception:
                body_str = "[Binary data - unable to decode]"
            
            return jsonify({
                'id': req['id'],
                'hostname': req['hostname'],
                'method': req['method'],
                'path': req['path'],
                'headers': req['headers'],
                'body': body_str,
                'timestamp': req['timestamp'],
            }), 200
        
        # Decision endpoints should forward this is where the work happend
        @self.app.route('/api/requests/<request_id>/allow', methods=['POST'])
        def allow_request(request_id: str) -> Tuple[Dict[str, Any], int]:
            """Mark request as allowed (to be forwarded)"""
            return
        
        @self.app.route('/api/requests/<request_id>/block', methods=['POST'])
        def block_request(request_id: str) -> Tuple[Dict[str, Any], int]:
            """Mark request as blocked (will not be forwarded)"""
            success = self.storage.delete_request(request_id)
            if success:
                print(f"[+] Request {request_id} is BLOCKED")
                return jsonify({'status': 'blocked'}), 200
            else:
                return jsonify({'error': 'Failed to update status'}), 500
        
        # @self.app.route('/api/requests/<request_id>/modify', methods=['POST'])
        # def modify_request(request_id: str) -> Tuple[Dict[str, Any], int]:
        #     """Mark request as modified and save modifications"""
        #     try:
        #         data = flask_request.get_json()
        #         modified_body = data.get('body', '')
                
        #         self.storage.set_modified_body(request_id, modified_body)
        #         self.storage.update_request_status(request_id, 'modified')
                
        #         print(f"[+] Request {request_id} marked as MODIFIED")
        #         return jsonify({'status': 'modified'}), 200
        #     except Exception as e:
        #         return jsonify({'error': str(e)}), 400
        
        
        # Admin endpoints
        @self.app.route('/api/health', methods=['GET'])
        def health() -> Tuple[Dict[str, Any], int]:
            """Health check endpoint"""
            health_status = self.storage.get_health_status()
            if health_status['status'] == 'connected':
                return jsonify(health_status), 200
            else:
                return jsonify(health_status), 500
        
        @self.app.route('/api/stats', methods=['GET'])
        def get_stats() -> Tuple[Dict[str, Any], int]:
            """Get proxy statistics"""
            pending_ids = self.storage.get_pending_requests()
            return jsonify({
                'total_pending': len(pending_ids),
                'redis_health': self.storage.get_health_status()
            }), 200
        
    def run(self, debug: bool = False) -> None:
        """
        Run Flask API server
        
        Args:
            debug: Enable debug mode
        """
        print(f"[+] API listening on http://127.0.0.1:{self.port}")
        self.app.run(host='127.0.0.1', port=self.port, debug=debug) 