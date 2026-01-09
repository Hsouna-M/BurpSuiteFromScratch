"""
Request Interceptor Module
Handles HTTP request parsing and extraction from encrypted data
"""

import re
from typing import Dict, Tuple, Optional


class RequestInterceptor:
    """Parses and extracts request information from HTTP data"""
    
    @staticmethod
    def parse_request(raw_data: str) -> Dict[str, any]:
        """
        Parse HTTP request data into structured format

        Args:
            raw_data: Raw HTTP request data as string

        Returns:
            Dictionary containing parsed request details
        """
        try:
            # Split headers and body
            parts = raw_data.split('\r\n\r\n', 1)
            header_part = parts[0]
            body = parts[1] if len(parts) > 1 else ""

            lines = header_part.split('\r\n')

            if not lines:
                return RequestInterceptor._empty_request()

            # Parse request line
            request_line = lines[0]
            method, path, version = RequestInterceptor._parse_request_line(request_line)

            # Parse headers
            headers = RequestInterceptor._parse_headers(lines[1:])

            return {
                'method': method,
                'path': path,
                'version': version,
                'headers': headers,
                'body': body
            }

        except Exception as e:
            print(f"[-] Error parsing request: {e}")
            return RequestInterceptor._empty_request()


    @staticmethod
    def _parse_request_line(line: str) -> Tuple[str, str, str]:
        """
        Parse HTTP request line (e.g., GET /path HTTP/1.1)
        
        Args:
            line: Request line string
            
        Returns:
            Tuple of (method, path, version)
        """
        try:
            parts = line.split()
            method = parts[0] if len(parts) > 0 else "UNKNOWN"
            path = parts[1] if len(parts) > 1 else "/"
            version = parts[2] if len(parts) > 2 else "HTTP/1.1"
            return method, path, version
        except Exception:
            return "UNKNOWN", "/", "HTTP/1.1"
    
    @staticmethod
    def _parse_headers(header_lines: list) -> Dict[str, str]:
        """
        Parse HTTP headers from lines
        
        Args:
            header_lines: List of header lines
            
        Returns:
            Dictionary of headers
        """
        headers = {}
        
        for line in header_lines:
            if not line:  # Empty line signals end of headers
                break
            
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip()] = value.strip()
        
        return headers
    
    @staticmethod
    def _empty_request() -> Dict:
        """Return empty request structure"""
        return {
            'method': 'UNKNOWN',
            'path': '/',
            'version': 'HTTP/1.1',
            'headers': {},
            'raw': ''
        }
    
    @staticmethod
    def extract_hostname(request_line: str) -> Optional[str]:
        """
        Extract hostname from CONNECT request line
        
        Args:
            request_line: CONNECT request line (e.g., CONNECT example.com:443 HTTP/1.1)
            
        Returns:
            Hostname or None
        """
        try:
            if not request_line.startswith("CONNECT"):
                return None
            
            parts = request_line.split()
            if len(parts) < 2:
                return None
            
            host_port = parts[1]
            hostname = host_port.split(':')[0]
            return hostname
        except Exception:
            return None
    
    @staticmethod
    def is_connect_request(request_line: str) -> bool:
        """
        Check if request is a CONNECT (tunnel) request
        
        Args:
            request_line: Request line string
            
        Returns:
            True if CONNECT request, False otherwise
        """
        return request_line.strip().startswith("CONNECT")