#!/usr/bin/env python3
"""
GUI Application
Web interface for inspecting and managing intercepted requests
"""

from flask import Flask, render_template, jsonify
import requests
import json


class ProxyGUI:
    """Web GUI for MITM Proxy"""
    
    def __init__(self, proxy_api_url: str = "http://127.0.0.1:9000", port: int = 5000):
        """
        Initialize GUI
        
        Args:
            proxy_api_url: URL of the proxy API
            port: Port to listen on
        """
        self.proxy_api_url = proxy_api_url
        self.port = port
        self.app = Flask(__name__)
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Setup Flask routes"""
        
        @self.app.route('/')
        def index():
            """Serve main GUI page"""
            return render_template('index.html')
        
        # Request listing
        @self.app.route('/api/requests')
        def get_requests():
            """Get pending requests from proxy API"""
            try:
                response = requests.get(
                    f'{self.proxy_api_url}/api/requests',
                    timeout=5
                )
                return jsonify(response.json())
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/requests/<request_id>')
        def get_request_details(request_id):
            """Get full request details from proxy API"""
            try:
                response = requests.get(
                    f'{self.proxy_api_url}/api/requests/{request_id}',
                    timeout=5
                )
                return jsonify(response.json())
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/responses/<request_id>')
        def get_response(request_id):
            """Get response details from proxy API"""
            try:
                response = requests.get(
                    f'{self.proxy_api_url}/api/responses/{request_id}',
                    timeout=5
                )
                if response.status_code == 404:
                     return jsonify({'error': 'Response not found'}), 404
                return jsonify(response.json())
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        # Request actions
        @self.app.route('/api/requests/<request_id>/allow', methods=['POST'])
        def allow_request(request_id):
            """Send allow decision to proxy API, with optional data"""
            try:
                from flask import request as flask_request
                data = flask_request.get_json(silent=True)
                response = requests.post(
                    f'{self.proxy_api_url}/api/requests/{request_id}/allow',
                    json=data,
                    timeout=5
                )
                return jsonify(response.json())
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/responses/<request_id>/allow', methods=['POST'])
        def allow_response(request_id):
            """Send allow decision for response to proxy API, with optional data"""
            try:
                from flask import request as flask_request
                data = flask_request.get_json(silent=True)
                response = requests.post(
                    f'{self.proxy_api_url}/api/responses/{request_id}/allow',
                    json=data,
                    timeout=5
                )
                return jsonify(response.json())
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/requests/<request_id>/block', methods=['POST'])
        def block_request(request_id):
            """Send block decision to proxy API"""
            try:
                response = requests.post(
                    f'{self.proxy_api_url}/api/requests/{request_id}/block',
                    timeout=5
                )
                return jsonify(response.json())
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/requests/<request_id>/delete', methods=['DELETE'])
        def delete_request(request_id):
            """Send delete decision to proxy API"""
            try:
                response = requests.delete(
                    f'{self.proxy_api_url}/api/requests/{request_id}',
                    timeout=5
                )
                return jsonify(response.json())
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        # Health and stats
        @self.app.route('/api/health')
        def health():
            """Check if proxy API is reachable"""
            try:
                response = requests.get(
                    f'{self.proxy_api_url}/api/health',
                    timeout=5
                )
                return jsonify(response.json())
            except Exception as e:
                return jsonify({'status': 'unhealthy', 'error': str(e)}), 500
        
        @self.app.route('/api/stats')
        def stats():
            """Get proxy statistics"""
            try:
                response = requests.get(
                    f'{self.proxy_api_url}/api/stats',
                    timeout=5
                )
                return jsonify(response.json())
            except Exception as e:
                return jsonify({'error': str(e)}), 500
    
    
        # -------------------------------------------------------------------------
        # Config Pass-through Routes
        # -------------------------------------------------------------------------

        @self.app.route('/api/config/mode', methods=['GET', 'POST'])
        def config_mode():
            """Proxy config mode"""
            try:
                from flask import request as flask_request
                if flask_request.method == 'GET':
                    resp = requests.get(f'{self.proxy_api_url}/api/config/mode', timeout=5)
                else:
                    resp = requests.post(f'{self.proxy_api_url}/api/config/mode', json=flask_request.get_json(silent=True), timeout=5)
                    
                if resp.status_code == 200:
                    return jsonify(resp.json()), 200
                else:
                    return jsonify(resp.json()), resp.status_code
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/config/domains', methods=['GET', 'POST'])
        def config_domains():
            """Proxy config domains"""
            try:
                from flask import request as flask_request
                if flask_request.method == 'GET':
                    resp = requests.get(f'{self.proxy_api_url}/api/config/domains', timeout=5)
                else:
                    resp = requests.post(f'{self.proxy_api_url}/api/config/domains', json=flask_request.get_json(silent=True), timeout=5)
                
                if resp.status_code == 200:
                    return jsonify(resp.json()), 200
                else:
                    return jsonify(resp.json()), resp.status_code
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/config/domains/<path:domain>', methods=['DELETE'])
        def config_domains_delete(domain):
            """Proxy config domains delete"""
            try:
                resp = requests.delete(f'{self.proxy_api_url}/api/config/domains/{domain}', timeout=5)
                if resp.status_code == 200:
                    return jsonify(resp.json()), 200
                else:
                    return jsonify(resp.json()), resp.status_code
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/config/keywords', methods=['GET', 'POST'])
        def config_keywords():
            """Proxy config keywords"""
            try:
                from flask import request as flask_request
                if flask_request.method == 'GET':
                    resp = requests.get(f'{self.proxy_api_url}/api/config/keywords', timeout=5)
                else:
                    resp = requests.post(f'{self.proxy_api_url}/api/config/keywords', json=flask_request.get_json(silent=True), timeout=5)
                
                if resp.status_code == 200:
                    return jsonify(resp.json()), 200
                else:
                    return jsonify(resp.json()), resp.status_code
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/config/keywords/<path:keyword>', methods=['DELETE'])
        def config_keywords_delete(keyword):
            """Proxy config keywords delete"""
            try:
                resp = requests.delete(f'{self.proxy_api_url}/api/config/keywords/{keyword}', timeout=5)
                if resp.status_code == 200:
                    return jsonify(resp.json()), 200
                else:
                    return jsonify(resp.json()), resp.status_code
            except Exception as e:
                return jsonify({'error': str(e)}), 500

    def run(self, debug: bool = True) -> None:
        """
        Run GUI server
        
        Args:
            debug: Enable debug mode
        """
        print(f"[+] GUI listening on http://127.0.0.1:{self.port}")
        print(f"[*] Proxy API: {self.proxy_api_url}")
        self.app.run(host='127.0.0.1', port=self.port, debug=debug)


def main():
    """Main entry point"""
    gui = ProxyGUI(
        proxy_api_url="http://127.0.0.1:9000",
        port=5000
    )
    gui.run(debug=False)


if __name__ == '__main__':
    main()