# utils/cors_helpers.py
from flask import jsonify

# Helper for CORS preflight response
def build_cors_preflight_response():
    response = jsonify({'message': 'Preflight success'})
    response.headers.add('Access-Control-Allow-Origin', 'https://nexusbot-connect.web.app')
    response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
    response.headers.add('Access-Control-Allow-Headers', 'Authorization, Content-Type')
    return response
