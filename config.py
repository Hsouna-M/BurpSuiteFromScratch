"""
Configuration Module
Centralized configuration for all components
"""

# Proxy Server Configuration
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8888

# API Server Configuration
API_HOST = "127.0.0.1"
API_PORT = 9000

# GUI Configuration
GUI_HOST = "127.0.0.1"
GUI_PORT = 5000

# Certificate Configuration
CA_CERT_FILE = "ca_cert.pem"
CA_KEY_FILE = "ca_key.pem"
CERT_CACHE_DIR = "certs"
CERT_VALIDITY_DAYS = 30

# Redis Configuration
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_REQUEST_EXPIRATION = 3600  # 1 hour

# Request Handling Configuration
REQUEST_TIMEOUT_SECONDS = 30
REQUEST_READ_BUFFER_SIZE = 4096

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "[%(levelname)s] %(message)s"

# Feature Flags
ENABLE_REQUEST_FORWARDING = False
ENABLE_REQUEST_MODIFICATION = True
ENABLE_REQUEST_BLOCKING = True

# Security Configuration
ALLOW_CLEAR_ALL = False  # Require confirmation to clear all requests
SSL_PROTOCOL = "TLS_SERVER"
SSL_CIPHER_SUITES = None  # Use default