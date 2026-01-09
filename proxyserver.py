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
import requests

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
                self._handle_http_request(client_socket, request_line, data)
        
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
            
            # -----------------------------------------------------------------
            # Filter Mode Check
            # -----------------------------------------------------------------
            if self.storage.get_proxy_mode() == 'filter':
                # Check Blocked Domains
                blocked_domains = self.storage.get_blocked_domains()
                if hostname in blocked_domains:
                     print(f"[!] Request to {hostname} BLOCKED by Filter Mode")
                     html_content = "<html><body><h1>Access Denied</h1><p>The domain <b>{}</b> is blocked by the proxy.</p></body></html>".format(hostname)
                     response = "HTTP/1.1 403 Forbidden\r\nContent-Type: text/html\r\nContent-Length: {}\r\n\r\n{}".format(len(html_content), html_content)
                     ssl_socket.send(response.encode())
                     return

                # Forward Request Automatically
                print(f"[!] Filter Mode: Auto-forwarding to {hostname}...")
                try:
                    url = f"https://{hostname}{path}"
                    response = requests.request(
                        method=method,
                        url=url,
                        headers=headers,
                        data=body,
                        verify=False,
                        allow_redirects=False
                    )
                    
                    # Check Blocked Keywords in Response
                    blocked_keywords = self.storage.get_blocked_keywords()
                    resp_content = response.text
                    
                    for keyword in blocked_keywords:
                        if keyword in resp_content:
                            print(f"[!] Response from {hostname} BLOCKED by Filter Mode (Keyword: {keyword})")
                            html_content = "<html><body><h1>Access Denied</h1><p>The response contained a blocked keyword: <b>{}</b></p></body></html>".format(keyword)
                            resp_str = "HTTP/1.1 403 Forbidden\r\nContent-Type: text/html\r\nContent-Length: {}\r\n\r\n{}".format(len(html_content), html_content)
                            ssl_socket.send(resp_str.encode())
                            return

                    # Forward Response
                    status_line = f"HTTP/1.1 {response.status_code} OK\r\n"
                    ssl_socket.send(status_line.encode())
                    
                    for key, value in response.headers.items():
                        if key.lower() in ['transfer-encoding', 'content-encoding', 'content-length']:
                            continue
                        header_line = f"{key}: {value}\r\n"
                        ssl_socket.send(header_line.encode())
                    
                    ssl_socket.send(f"Content-Length: {len(response.content)}\r\n".encode())
                    ssl_socket.send(b"\r\n")
                    ssl_socket.send(response.content)
                    print(f"[+] Response forwarded (Filter Mode)")
                    return

                except Exception as e:
                    print(f"[-] Error forwarding in Filter Mode: {e}")
                    ssl_socket.send(b"HTTP/1.1 502 Bad Gateway\r\n\r\nProxy Error")
                    return

            # -----------------------------------------------------------------
            # Intercept Mode (Original Logic)
            # -----------------------------------------------------------------
            
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
            # Wait for GUI decision (max 60 seconds)
            max_wait = 60
            waited = 0
            status = 'pending'
            
            while waited < max_wait:
                status = self.storage.get_request_status(request_id)
                if status != 'pending':
                    print(f"[+] Request status: {status}")
                    break
                time.sleep(0.5)
                waited += 0.5
            
            # Handle based on status
            if status == 'blocked':
                print(f"[!] Request blocked by user")
                ssl_socket.send(b"HTTP/1.1 403 Forbidden\r\n\r\nBlocked by proxy")
            
            elif status == 'allowed':
                # Reload request data in case it was modified
                req_data = self.storage.get_request(request_id)
                if req_data:
                    method = req_data['method']
                    path = req_data['path']
                    headers = req_data['headers']
                    # Check if body was modified (stored as string/hex)
                    # For now assume string if modified
                    if 'body' in req_data:
                        body = req_data['body']
                
                # Remove Accept-Encoding to avoid compressed responses we can't handle (like brotli)
                # requests will add its own acceptable encodings (gzip, deflate) and decode automatically
                if 'Accept-Encoding' in headers:
                    del headers['Accept-Encoding']
                # Case-insensitive check just in case
                for k in list(headers.keys()):
                    if k.lower() == 'accept-encoding':
                        del headers[k]

                print(f"[!] Request allowed - Forwarding to {hostname}...")
                
                try:
                    # Construct URL
                    url = f"https://{hostname}{path}"
                    
                    # Forward request using requests library
                    response = requests.request(
                        method=method,
                        url=url,
                        headers=headers,
                        data=body,
                        verify=False,  # Ignore SSL verify for upstream
                        allow_redirects=False 
                    )
                    
                    print(f"[+] Received response from server: {response.status_code}")
                    
                    # Save response to Redis
                    self.storage.save_response(
                        request_id=request_id,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        body=response.text 
                    )
                    
                    # Wait for Response Decision
                    print(f"[*] Waiting for RESPONSE decision...")
                    resp_waited = 0
                    resp_status = 'pending'
                    while resp_waited < max_wait:
                        resp_status = self.storage.get_response_status(request_id)
                        if resp_status != 'pending':
                             break
                        time.sleep(0.5)
                        resp_waited += 0.5
                    
                    if resp_status == 'allowed':
                        # Reload response data in case it was modified
                        stored_resp = self.storage.get_response(request_id)
                        resp_status_code = response.status_code
                        resp_headers = dict(response.headers)
                        resp_body = response.content
                        
                        if stored_resp:
                            resp_status_code = int(stored_resp.get('status_code', response.status_code))
                            resp_headers = stored_resp.get('headers', resp_headers)
                            resp_body_str = stored_resp.get('body')
                            if resp_body_str is not None:
                                resp_body = resp_body_str.encode('utf-8')

                        # Send response back to client
                        # Construct status line
                        status_line = f"HTTP/1.1 {resp_status_code} OK\r\n" # Simplified reason
                        ssl_socket.send(status_line.encode())
                        
                        # Send headers
                        for key, value in resp_headers.items():
                            if key.lower() == 'transfer-encoding' or key.lower() == 'content-encoding':
                                continue
                            # Update content-length if body changed
                            if key.lower() == 'content-length':
                                value = str(len(resp_body))
                                
                            header_line = f"{key}: {value}\r\n"
                            ssl_socket.send(header_line.encode())
                        
                        ssl_socket.send(b"\r\n")
                        
                        # Send body
                        ssl_socket.send(resp_body)
                        print(f"[+] Response forwarded to client")
                        
                    elif resp_status == 'blocked':
                         ssl_socket.send(b"HTTP/1.1 403 Forbidden\r\n\r\nBlocked by proxy")
                    else:
                         ssl_socket.send(b"HTTP/1.1 504 Gateway Timeout\r\n\r\nResponse decision timeout")
                    
                except Exception as e:
                    print(f"[-] Error forwarding HTTPS request: {e}")
                    ssl_socket.send(b"HTTP/1.1 502 Bad Gateway\r\n\r\nProxy Error")
                    
            elif status == 'modified':
                # Similar to allowed but use modified body/headers if implemented
                print(f"[!] Request modified (using allowed path for now)")
                # For now fallthrough to blocked or implement same as allowed but with modified data
                ssl_socket.send(b"HTTP/1.1 501 Not Implemented\r\n\r\nModified requests not yet implemented")
                
            else:
                print(f"[-] Timeout waiting for decision")
                ssl_socket.send(b"HTTP/1.1 408 Request Timeout\r\n\r\n")
        
        except Exception as e:
            print(f"[-] Error reading encrypted data: {e}")
        finally:
            try:
                ssl_socket.close()
            except:
                pass
    
    def _handle_http_request(self, client_socket: socket.socket, request_line: str, initial_data: bytes) -> None:
        """
        Handle plain HTTP request (non-HTTPS)
        
        Args:
            client_socket: Client socket
            request_line: HTTP request line
            initial_data: Initial data received from client
        """
        try:
            # Decode request
            try:
                request_str = initial_data.decode('utf-8', errors='ignore')
            except Exception:
                request_str = "[Binary data]"
            
            print(f"[+] HTTP request received:\n{request_str[:200]}")
            
            # Parse request
            parsed = RequestInterceptor.parse_request(request_str)
            method = parsed['method']
            path = parsed['path']
            headers = parsed['headers']
            body = parsed['body']
            
            # Extract hostname from Host header
            hostname = headers.get('Host', '')
            if not hostname:
                 # Fallback if full URL in path
                 if '://' in path:
                     hostname = path.split('://')[1].split('/')[0]
            
            # -----------------------------------------------------------------
            # Filter Mode Check
            # -----------------------------------------------------------------
            if self.storage.get_proxy_mode() == 'filter':
                # Check Blocked Domains
                blocked_domains = self.storage.get_blocked_domains()
                if hostname in blocked_domains:
                     print(f"[!] Request to {hostname} BLOCKED by Filter Mode")
                     html_content = "<html><body><h1>Access Denied</h1><p>The domain <b>{}</b> is blocked by the proxy.</p></body></html>".format(hostname)
                     response = "HTTP/1.1 403 Forbidden\r\nContent-Type: text/html\r\nContent-Length: {}\r\n\r\n{}".format(len(html_content), html_content)
                     client_socket.send(response.encode())
                     return

                # Forward Request Automatically
                print(f"[!] Filter Mode: Auto-forwarding to {hostname}...")
                try:
                    if path.startswith('http://'):
                         url = path
                    else:
                         clean_path = path if path.startswith('/') else f"/{path}"
                         url = f"http://{hostname}{clean_path}"
                    
                    response = requests.request(
                        method=method,
                        url=url,
                        headers=headers,
                        data=body,
                        allow_redirects=False
                    )
                    
                    # Check Blocked Keywords in Response
                    blocked_keywords = self.storage.get_blocked_keywords()
                    resp_content = response.text
                    
                    for keyword in blocked_keywords:
                        if keyword in resp_content:
                            print(f"[!] Response from {hostname} BLOCKED by Filter Mode (Keyword: {keyword})")
                            html_content = "<html><body><h1>Access Denied</h1><p>The response contained a blocked keyword: <b>{}</b></p></body></html>".format(keyword)
                            resp_str = "HTTP/1.1 403 Forbidden\r\nContent-Type: text/html\r\nContent-Length: {}\r\n\r\n{}".format(len(html_content), html_content)
                            client_socket.send(resp_str.encode())
                            return

                    # Forward Response
                    status_line = f"HTTP/1.1 {response.status_code} OK\r\n"
                    client_socket.send(status_line.encode())
                    
                    for key, value in response.headers.items():
                        if key.lower() in ['transfer-encoding', 'content-encoding', 'content-length']:
                            continue
                        header_line = f"{key}: {value}\r\n"
                        client_socket.send(header_line.encode())
                    
                    client_socket.send(f"Content-Length: {len(response.content)}\r\n".encode())
                    client_socket.send(b"\r\n")
                    client_socket.send(response.content)
                    print(f"[+] Response forwarded (Filter Mode)")
                    return

                except Exception as e:
                    print(f"[-] Error forwarding in Filter Mode: {e}")
                    client_socket.send(b"HTTP/1.1 502 Bad Gateway\r\n\r\nProxy Error")
                    return

            # -----------------------------------------------------------------
            # Intercept Mode (Original Logic)
            # -----------------------------------------------------------------

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
            
            # Wait for GUI decision (max 60 seconds)
            max_wait = 60
            waited = 0
            status = 'pending'
            
            while waited < max_wait:
                status = self.storage.get_request_status(request_id)
                if status != 'pending':
                    print(f"[+] Request status: {status}")
                    break
                time.sleep(0.5)
                waited += 0.5
                
            # Handle based on status
            if status == 'blocked':
                print(f"[!] Request blocked by user")
                client_socket.send(b"HTTP/1.1 403 Forbidden\r\n\r\nBlocked by proxy")
                
            elif status == 'allowed':
                # Reload request data in case it was modified
                req_data = self.storage.get_request(request_id)
                if req_data:
                    method = req_data['method']
                    path = req_data['path']
                    headers = req_data['headers']
                    if 'body' in req_data:
                        body = req_data['body']

                # Remove Accept-Encoding to avoid compressed responses we can't handle (like brotli)
                if 'Accept-Encoding' in headers:
                    del headers['Accept-Encoding']
                for k in list(headers.keys()):
                    if k.lower() == 'accept-encoding':
                        del headers[k]

                print(f"[!] Request allowed - Forwarding to {hostname}...")
                
                try:
                    # Construct URL. Handle if path is already full URL
                    if path.startswith('http://'):
                         url = path
                    else:
                         clean_path = path if path.startswith('/') else f"/{path}"
                         url = f"http://{hostname}{clean_path}"
                    
                    # Forward request using requests library
                    response = requests.request(
                        method=method,
                        url=url,
                        headers=headers,
                        data=body,
                        allow_redirects=False
                    )
                    
                    print(f"[+] Received response from server: {response.status_code}")
                    
                    # Save response to Redis
                    self.storage.save_response(
                        request_id=request_id,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        body=response.text
                    )
                    
                    # Wait for Response Decision
                    print(f"[*] Waiting for RESPONSE decision...")
                    resp_waited = 0
                    resp_status = 'pending'
                    while resp_waited < max_wait:
                        resp_status = self.storage.get_response_status(request_id)
                        if resp_status != 'pending':
                             break
                        time.sleep(0.5)
                        resp_waited += 0.5
                    
                    if resp_status == 'allowed':
                        # Reload response data in case it was modified
                        stored_resp = self.storage.get_response(request_id)
                        resp_status_code = response.status_code
                        resp_headers = dict(response.headers)
                        resp_body = response.content
                        
                        if stored_resp:
                            resp_status_code = int(stored_resp.get('status_code', response.status_code))
                            resp_headers = stored_resp.get('headers', resp_headers)
                            resp_body_str = stored_resp.get('body')
                            if resp_body_str is not None:
                                resp_body = resp_body_str.encode('utf-8')

                        # Send response back to client
                        status_line = f"HTTP/1.1 {resp_status_code} OK\r\n"
                        client_socket.send(status_line.encode())
                        
                        # Send headers
                        for key, value in resp_headers.items():
                            if key.lower() == 'transfer-encoding' or key.lower() == 'content-encoding':
                                continue
                            if key.lower() == 'content-length':
                                value = str(len(resp_body))
                            header_line = f"{key}: {value}\r\n"
                            client_socket.send(header_line.encode())
                        
                        client_socket.send(b"\r\n")
                        
                        # Send body
                        client_socket.send(resp_body)
                        print(f"[+] Response forwarded to client")
                        
                    elif resp_status == 'blocked':
                         client_socket.send(b"HTTP/1.1 403 Forbidden\r\n\r\nBlocked by proxy")
                    else:
                         client_socket.send(b"HTTP/1.1 504 Gateway Timeout\r\n\r\nResponse decision timeout")
                    
                except Exception as e:
                    print(f"[-] Error forwarding HTTP request: {e}")
                    client_socket.send(b"HTTP/1.1 502 Bad Gateway\r\n\r\nProxy Error")
                    
            elif status == 'modified':
                 client_socket.send(b"HTTP/1.1 501 Not Implemented\r\n\r\nModified requests not yet implemented")
                 
            else:
                 print(f"[-] Timeout waiting for decision")
                 client_socket.send(b"HTTP/1.1 408 Request Timeout\r\n\r\n")

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