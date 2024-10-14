# utils/cors_helpers.py
from flask import jsonify, request

# Helper for CORS preflight response
def build_cors_preflight_response():
    origin = request.headers.get('Origin')
    allowed_origins = [
       "https://nexusbot-connect.web.app", 
                                         "https://nexusbot-connect.firebaseapp.com",
                                         "https://nexusbot.app",
                                         "https://api.nexusbot.app", 
                                         "http://localhost:8080", 
                                         "http://192.168.1.229:8080",
    ]
    
    if origin in allowed_origins:
        response = jsonify({'message': 'Preflight success'})
        response.headers.add('Access-Control-Allow-Origin', origin)
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        return response
    else:
        return jsonify({'message': 'Origin not allowed'}), 403
