#!/usr/bin/env python3
"""
Minimal MITM Proxy - Educational Implementation
Demonstrates SSL/TLS interception and certificate spoofing
"""

import socket
import ssl
import threading
import os
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import re

# Configuration
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8888
CA_CERT_FILE = "ca_cert.pem"
CA_KEY_FILE = "ca_key.pem"
CERT_CACHE_DIR = "certs"

class CertificateAuthority:
    """Generates and manages certificates"""
    
    def __init__(self, cert_file, key_file):
        self.cert_file = cert_file
        self.key_file = key_file
        
        if not os.path.exists(cert_file) or not os.path.exists(key_file):
            self.generate_ca_certificate()
        else:
            self.load_ca_certificate()
    
    def generate_ca_certificate(self):
        """Generate self-signed CA certificate"""
        print("[*] Generating CA certificate...")
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Create certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MITM Proxy"),
            x509.NameAttribute(NameOID.COMMON_NAME, "MITM Proxy CA"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365)
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        ).sign(private_key, hashes.SHA256(), default_backend())
        
        # Save to files
        with open(self.cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        with open(self.key_file, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        self.ca_cert = cert
        self.ca_key = private_key
        print(f"[+] CA certificate saved to {self.cert_file}")
    
    def load_ca_certificate(self):
        """Load existing CA certificate"""
        with open(self.cert_file, "rb") as f:
            self.ca_cert = x509.load_pem_x509_certificate(
                f.read(), default_backend()
            )
        
        with open(self.key_file, "rb") as f:
            self.ca_key = serialization.load_pem_private_key(
                f.read(), password=None, backend=default_backend()
            )
    
    def generate_certificate(self, hostname):
        """Generate certificate for hostname signed by CA"""
        # Generate server private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Create certificate
        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            self.ca_cert.issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=30)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(hostname),
                x509.DNSName(f"*.{hostname}"),
            ]),
            critical=False,
        ).sign(self.ca_key, hashes.SHA256(), default_backend())
        
        return cert, private_key


class MITMProxy:
    """Minimal MITM Proxy"""
    
    def __init__(self, host, port, ca):
        self.host = host
        self.port = port
        self.ca = ca
        
        if not os.path.exists(CERT_CACHE_DIR):
            os.makedirs(CERT_CACHE_DIR)
    
    def start(self):
        """Start proxy server"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(5)
        
        print(f"[+] Proxy listening on {self.host}:{self.port}")
        
        try:
            while True:
                client_socket, client_addr = server.accept()
                print(f"[*] Connection from {client_addr}")
                
                thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, client_addr)
                )
                thread.daemon = True
                thread.start()
        except KeyboardInterrupt:
            print("\n[*] Shutting down...")
            server.close()
    
    def handle_client(self, client_socket, client_addr):
        """Handle client connection"""
        try:
            # Read first request line
            data = client_socket.recv(1024)
            request_line = data.split(b'\r\n')[0].decode()
            print(f"[*] Request: {request_line}")
            
            # Extract hostname from CONNECT request
            if request_line.startswith("CONNECT"):
                host_port = request_line.split()[1]
                hostname = host_port.split(':')[0]
                
                # Generate certificate for hostname
                cert, key = self.ca.generate_certificate(hostname)
                
                # Save certificate and key
                cert_path = os.path.join(CERT_CACHE_DIR, f"{hostname}.crt")
                key_path = os.path.join(CERT_CACHE_DIR, f"{hostname}.key")
                
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
                
                # Wrap socket with SSL using generated certificate
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(cert_path, key_path)
                
                ssl_socket = context.wrap_socket(
                    client_socket, server_side=True
                )
                
                print(f"[+] Established HTTPS tunnel to {hostname}")
                
                # Read encrypted request
                try:
                    encrypted_data = ssl_socket.recv(1024)
                    decrypted_request = encrypted_data.decode()
                    print(f"[+] Decrypted request:\n{decrypted_request[:200]}")
                except Exception as e:
                    print(f"[-] Error reading encrypted data: {e}")
                
                ssl_socket.close()
            else:
                # HTTP request
                print(f"[+] HTTP request received")
                client_socket.send(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nHello from MITM Proxy")
        
        except Exception as e:
            print(f"[-] Error: {e}")
        finally:
            client_socket.close()

if __name__ == "__main__":
    ca = CertificateAuthority(CA_CERT_FILE, CA_KEY_FILE)
    proxy = MITMProxy(PROXY_HOST, PROXY_PORT, ca)
    proxy.start()