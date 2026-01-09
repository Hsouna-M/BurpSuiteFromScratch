#!/usr/bin/env python3
"""
MITM Proxy Server
Main entry point for the MITM proxy with Redis backend
"""

import socket
import ssl
import threading
import os
import uuid
import time
from datetime import datetime
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from certificate_authority import CertificateAuthority
from redis_storage import RedisStorage
from request_interceptor import RequestInterceptor
from proxy_api import ProxyAPI


class MITMProxyServer:
    """Main MITM Proxy Server"""
    
    def __init__(
        self,
        proxy_host: str = "127.0.0.1",
        proxy_port: int = 8888,
        api_port: int = 9000,
        cert_file: str = "ca_cert.pem",
        key_file: str = "ca_key.pem",
        cert_cache_dir: str = "certs",
        redis_host: str = "localhost",
        redis_port: int = 6379
    ):
        """
        Initialize MITM Proxy Server
        
        Args:
            proxy_host: Host to listen on
            proxy_port: Port to listen on
            api_port: Port for Flask API
            cert_file: Path to CA certificate
            key_file: Path to CA private key
            cert_cache_dir: Directory to cache generated certificates
            redis_host: Redis host
            redis_port: Redis port
        """
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.api_port = api_port
        self.cert_cache_dir = cert_cache_dir
        
        # Initialize components
        self.ca = CertificateAuthority(cert_file, key_file)
        self.storage = RedisStorage(host=redis_host, port=redis_port)
        self.api = ProxyAPI(self.storage, port=api_port)
        
    def _start_api_server(self) -> None:
        """Start Flask API in background thread"""
        api_thread = threading.Thread(
            target=self.api.run,
            kwargs={'debug': False},
            daemon=True
        )
        api_thread.start()
    
    def start(self) -> None:
        """Start the proxy server"""
        # Start API server
        self._start_api_server()
        
        # Start proxy server
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #allows for reuse even when the socket is in the Time_Wait state
        server.bind((self.proxy_host, self.proxy_port))
        server.listen(5)
        
        print(f"[+] MITM Proxy listening on {self.proxy_host}:{self.proxy_port}")
        print(f"[+] Configure browser proxy to: http://{self.proxy_host}:{self.proxy_port}")
        
        try:
            while True:
                client_socket, client_addr = server.accept()
                
                # Handle client in separate thread
                thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_addr),
                    daemon=True
                )
                thread.start()
        except KeyboardInterrupt:
            print("\n[*] Shutting down proxy server...")
            os.system("rm -R ./certs/*")
            self.storage.flush_all_instances()
            server.close()
    
    def _handle_client(self, client_socket: socket.socket, client_addr: tuple) -> None:
        """
        Handle client connection
        
        Args:
            client_socket: Client socket
            client_addr: Client address tuple
        """
        try:
            # Receive initial request
            data = client_socket.recv(1024)
            
            if not data:
                client_socket.close()
                return
            
            request_line = data.split(b'\r\n')[0].decode()
            print(f"[*] Connection from {client_addr[0]}:{client_addr[1]}")
            print(f"[*] Request: {request_line}")
            
            # Check if this is a CONNECT request (for HTTPS tunneling)
            if RequestInterceptor.is_connect_request(request_line):
                self._handle_connect_request(client_socket, request_line)
            else:
                self._handle_http_request(client_socket, request_line)
        
        except Exception as e:
            print(f"[-] Error handling client: {e}")
        finally:
            client_socket.close()
    
    def _handle_connect_request(self, client_socket: socket.socket, request_line: str) -> None:
        """
        Handle CONNECT request (HTTPS tunneling)
        
        Args:
            client_socket: Client socket
            request_line: CONNECT request line
        """
        try:
            # Extract hostname
            hostname = RequestInterceptor.extract_hostname(request_line)
            
            if not hostname:
                client_socket.send(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                return
            
            # Generate certificate for hostname
            cert, key = self.ca.generate_certificate(hostname)
            
            # Save certificate and key to cache
            cert_path = os.path.join(self.cert_cache_dir, f"{hostname}.crt")
            key_path = os.path.join(self.cert_cache_dir, f"{hostname}.key")
            
            with open(cert_path, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            
            with open(key_path, "wb") as f:
                f.write(key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            
            # Send 200 response to establish tunnel
            client_socket.send(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            
            # Wrap socket with SSL
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert_path, key_path)
            ssl_socket = context.wrap_socket(client_socket, server_side=True)
            
            print(f"[+] Established HTTPS tunnel to {hostname}")
            
            # Read encrypted request
            self._read_and_store_request(ssl_socket, hostname)
        
        except Exception as e:
            print(f"[-] Error handling CONNECT request: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
    
    def _read_and_store_request(self, ssl_socket: socket.socket, hostname: str) -> None:
        """
        Read encrypted request and store to Redis
        
        Args:
            ssl_socket: SSL wrapped socket
            hostname: Target hostname
        """
        try:
            encrypted_data = ssl_socket.recv(4096)
            
            if not encrypted_data:
                return
            
            # Decode request safely
            try:
                decrypted_request = encrypted_data.decode('utf-8', errors='ignore')
            except Exception:
                decrypted_request = "[Binary data]"
            
            print(f"[+] Decrypted request:\n{decrypted_request[:200]}")
            
            # Parse request
            parsed = RequestInterceptor.parse_request(decrypted_request)
            method = parsed['method']
            path = parsed['path']
            headers = parsed['headers']
            body = parsed['body']
            
            # Create unique request ID
            request_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            
            # Store to Redis
            self.storage.save_request(
                request_id=request_id,
                hostname=hostname,
                method=method,
                path=path,
                headers=headers,
                body=body,
                timestamp=timestamp
            )
            
            print(f"[+] Request {request_id} saved to Redis")
            print(f"[*] Waiting for GUI decision...")
            
            # Wait for GUI decision (max 30 seconds)
            # max_wait = 600 
            # waited = 0
            # status = 'pending'
            
            # while waited < max_wait:
            #     status = self.storage.get_request_status(request_id)
            #     if status != 'pending':
            #         print(f"[+] Request status: {status}")
            #         break
            #     time.sleep(0.5)
            #     waited += 0.5
            
            # # Handle based on status
            # if status == 'blocked':
            #     print(f"[!] Request blocked by user")
            #     ssl_socket.send(b"HTTP/1.1 403 Forbidden\r\n\r\nBlocked by proxy")
            # elif status == 'allowed':
            #     print(f"[!] Request allowed (forwarding not implemented yet)")
            #     ssl_socket.send(b"HTTP/1.1 200 OK\r\n\r\nAllowed by proxy")
            # elif status == 'modified':
            #     print(f"[!] Request modified (forwarding not implemented yet)")
            #     ssl_socket.send(b"HTTP/1.1 200 OK\r\n\r\nModified by proxy")
            # else:
            #     print(f"[-] Timeout waiting for decision")
            #     ssl_socket.send(b"HTTP/1.1 408 Request Timeout\r\n\r\n")
        
        except Exception as e:
            print(f"[-] Error reading encrypted data: {e}")
        finally:
            try:
                ssl_socket.close()
            except:
                pass
    
    def _handle_http_request(self, client_socket: socket.socket, request_line: str) -> None:
        """
        Handle plain HTTP request (non-HTTPS)
        
        Args:
            client_socket: Client socket
            request_line: HTTP request line
        """
        try:
            print(f"[+] HTTP request received")
            client_socket.send(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n"
                b"Hello from MITM Proxy"
            )
        except Exception as e:
            print(f"[-] Error handling HTTP request: {e}")


def main():
    """Main entry point"""
    proxy = MITMProxyServer(
        proxy_host="127.0.0.1",
        proxy_port=8888,
        api_port=9000,
        cert_file="ca_cert.pem",
        key_file="ca_key.pem",
        cert_cache_dir="certs",
        redis_host="localhost",
        redis_port=6379
    )
    
    proxy.start()


if __name__ == "__main__":
    main()