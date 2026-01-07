import socket
import threading
from flask import Flask, jsonify
from flask_socketio import SocketIO
from browser_handler import BrowserHandler
from tls_manager import TLSManager
from logger import Logger

app = Flask(__name__)
socketio = SocketIO(app, cors_sourat al maarij llowed_origins="*")


# Initialize components
logger = Logger()
tls_manager = TLSManager()

class ProxyServer:
    def __init__(self, port=8443, host='localhost'):
        self.port = port
        self.host = host
        self.server_socket = None
        self.running = False
    
    def start(self):
        """Start proxy server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
        self.running = True
        print(f"[ProxyServer] Listening on {self.host}:{self.port}")
        
        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                print(f"[ProxyServer] New connection from {client_address}")
                
                # Handle in separate thread
                handler = BrowserHandler(client_socket, client_address, logger, tls_manager)
                thread = threading.Thread(target=handler.run)
                thread.daemon = True
                thread.start()
            
            except Exception as e:
                print(f"[ProxyServer] Error: {e}")
    
    def stop(self):
        """Stop proxy server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()

# Flask routes for web interface
@app.route('/api/requêtes', methods=['GET'])
def get_requests():
    """Return all logged requests"""
    requests = logger.read_all_requests(limit=50)
    return jsonify(requests)

@app.route('/api/requête/<request_id>', methods=['GET'])
def get_request(request_id):
    """Return specific request"""
    request = logger.read_request(request_id)
    if request:
        return jsonify(request)
    return jsonify({'erreur': 'Requête non trouvée'}), 404

@app.route('/api/efface-journaux', methods=['POST'])
def clear_logs():
    """Clear all logs"""
    logger.clear_logs()
    return jsonify({'message': 'Journaux effacés'})

@app.route('/')
def index():
    """Serve web interface"""

    return app.send_static_file('index.html')

if __name__ == '__main__':
    # Start proxy in separate thread
    proxy = ProxyServer(port=8443, host='127.0.0.1')
    proxy_thread = threading.Thread(target=proxy.start)
    proxy_thread.daemon = True
    proxy_thread.start()
    
    # Start Flask web server
    print("[Main] Starting web interface on http://localhost:5000")
    socketio.run(app, host='127.0.0.1', port=5022, debug=True)