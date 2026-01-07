import ssl
import os

class TLSManager:
    def __init__(self, certfile='../certs/server.crt', keyfile='../certs/server.key'):
        self.certfile = certfile
        self.keyfile = keyfile
        self.context = None
    
    def create_context(self):
        """Create SSL context for server"""
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.load_cert_chain(self.certfile, self.keyfile)
        return self.context
    
    def wrap_socket(self, socket):
        """Wrap socket with TLS"""
        if self.context is None:
            self.create_context()
        return self.context.wrap_socket(socket, server_side=True)
    
    def encrypt(self, data):
        """Data is automatically encrypted by SSL socket"""
        return data
    
    def decrypt(self, data):
        """Data is automatically decrypted by SSL socket"""
        return data