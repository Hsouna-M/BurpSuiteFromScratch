import redis
import json
from datetime import datetime

class Logger:
    def __init__(self, host='localhost', port=6379):
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            decode_responses=True
        )
        self.request_counter = 0
    
    def log_request(self, request):
        """Log HTTP request to Redis"""
        self.request_counter += 1
        request_id = f"requête:{self.request_counter}"
        
        # Store as hash
        self.redis_client.hset(request_id, mapping={
            'méthode': request.get('méthode', ''),
            'url': request.get('url', ''),
            'version': request.get('version', ''),
            'en-têtes': json.dumps(request.get('en-têtes', {})),
            'corps': request.get('corps', ''),
            'horodatage': datetime.now().isoformat(),
            'type': 'requête'
        })
        
        # Add to list for easy retrieval
        self.redis_client.lpush('toutes_requêtes', request_id)
        
        # Keep only last 100 requests
        self.redis_client.ltrim('toutes_requêtes', 0, 99)
        
        return request_id
    
    def log_response(self, request_id, response):
        """Log HTTP response to Redis"""
        response_id = f"{request_id}:réponse"
        
        self.redis_client.hset(response_id, mapping={
            'codeStatut': response.get('codeStatut', ''),
            'en-têtes': json.dumps(response.get('en-têtes', {})),
            'corps': response.get('corps', ''),
            'horodatage': datetime.now().isoformat(),
            'type': 'réponse'
        })
        
        self.redis_client.lpush('toutes_réponses', response_id)
        self.redis_client.ltrim('toutes_réponses', 0, 99)
    
    def read_all_requests(self, limit=50):
        """Read all logged requests from Redis"""
        request_ids = self.redis_client.lrange('toutes_requêtes', 0, limit - 1)
        
        requests = []
        for req_id in request_ids:
            data = self.redis_client.hgetall(req_id)
            if data:
                # Parse headers back to dict
                data['en-têtes'] = json.loads(data.get('en-têtes', '{}'))
                requests.append({
                    'id': req_id,
                    **data
                })
        
        return requests
    
    def read_request(self, request_id):
        """Read specific request"""
        data = self.redis_client.hgetall(request_id)
        if data:
            data['en-têtes'] = json.loads(data.get('en-têtes', '{}'))
            return {'id': request_id, **data}
        return None
    
    def clear_logs(self):
        """Clear all logs"""
        self.redis_client.delete('toutes_requêtes')
        self.redis_client.delete('toutes_réponses')