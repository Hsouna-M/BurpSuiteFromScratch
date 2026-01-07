class RequestParser:
    def __init__(self):
        self.buffer = b''
    
    def parse_http(self, data):
        """Parse raw HTTP data into structured request"""
        self.buffer += data
        
        # Check if we have complete headers (look for \r\n\r\n)
        if b'\r\n\r\n' not in self.buffer:
            return None
        
        # Split headers and body
        header_end = self.buffer.find(b'\r\n\r\n')
        header_data = self.buffer[:header_end].decode('utf-8', errors='ignore')
        body_data = self.buffer[header_end + 4:]
        
        # Parse request line
        lines = header_data.split('\r\n')
        request_line = lines[0].split()
        
        request = {
            'méthode': request_line[0],
            'url': request_line[1],
            'version': request_line[2],
            'en-têtes': {},
            'corps': body_data.decode('utf-8', errors='ignore')
        }
        
        # Parse headers
        for line in lines[1:]:
            if ':' in line:
                key, value = line.split(':', 1)
                request['en-têtes'][key.strip()] = value.strip()
        
        # Clear buffer after parsing
        self.buffer = b''
        
        return request
    
    def validate(self, request):
        """Validate request structure"""
        required = ['méthode', 'url', 'version']
        return all(key in request for key in required)