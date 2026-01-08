"""
Certificate Authority Module
Handles generation and management of SSL/TLS certificates
"""

import os
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend


class CertificateAuthority:
    """Generates and manages SSL/TLS certificates for MITM interception"""
    
    def __init__(self, cert_file: str, key_file: str):
        """
        Initialize Certificate Authority
        
        Args:
            cert_file: Path to CA certificate file
            key_file: Path to CA private key file
        """
        self.cert_file = cert_file
        self.key_file = key_file
        
        if not os.path.exists(cert_file) or not os.path.exists(key_file):
            self.generate_ca_certificate()
        else:
            self.load_ca_certificate()
    
    def generate_ca_certificate(self) -> None:
        """Generate self-signed CA certificate and private key"""
        print("[*] Generating CA certificate...")
        
        # Generate 2048-bit RSA private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Create self-signed certificate
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
        
        # Write certificate to file
        with open(self.cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        # Write private key to file
        with open(self.key_file, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        self.ca_cert = cert
        self.ca_key = private_key
        print(f"[+] CA certificate generated and saved to {self.cert_file}")
    
    def load_ca_certificate(self) -> None:
        """Load existing CA certificate and private key from files"""
        print(f"[*] Loading CA certificate from {self.cert_file}")
        
        with open(self.cert_file, "rb") as f:
            self.ca_cert = x509.load_pem_x509_certificate(
                f.read(), default_backend()
            )
        
        with open(self.key_file, "rb") as f:
            self.ca_key = serialization.load_pem_private_key(
                f.read(), password=None, backend=default_backend()
            )
        
        print("[+] CA certificate loaded successfully")
    
    def generate_certificate(self, hostname: str) -> tuple:
        """
        Generate a certificate for a specific hostname, signed by the CA
        
        Args:
            hostname: The hostname to generate certificate for (e.g., 'example.com')
            
        Returns:
            Tuple of (certificate, private_key)
        """
        # Generate server private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Create certificate subject
        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        ])
        
        # Build and sign certificate
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