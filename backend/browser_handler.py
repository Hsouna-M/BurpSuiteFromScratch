import socket
import threading
from request_parser import RequestParser
from tls_manager import TLSManager

class BrowserHandler:
    def __init__(self, client_socket, client_address, logger, tls_manager):
        self.client_socket = client_socket
        self.client_address = client_address
        self.logger = logger
        self.tls_manager = tls_manager
        self.parser = RequestParser()
    
    def run(self):
        """Handle browser connection"""
        try:
            # Wrap with TLS
            ssl_socket = self.tls_manager.wrap_socket(self.client_socket)
            
            print(f"[BrowserHandler] TLS handshake complete with {self.client_address}")
            
            # Receive request
            data = ssl_socket.recv(4096)
            
            if data:
                # Parse request
                request = self.parser.parse_http(data)
                
                if request and self.parser.validate(request):
                    print(f"[BrowserHandler] Received: {request['méthode']} {request['url']}")
                    
                    # Log to Redis
                    request_id = self.logger.log_request(request)
                    print(f"[BrowserHandler] Logged request: {request_id}")
                    
                    # Send simple response (for now)
                    response = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: text/plain\r\n"
                        "Content-Length: 13\r\n"
                        "\r\n"
                        "Hello, World!"
                    )
                    ssl_socket.send(response.encode())
            
            ssl_socket.close()
        
        except Exception as e:
            print(f"[BrowserHandler] Error: {e}")
        finally:
            self.client_socket.close()