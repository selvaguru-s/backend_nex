from functools import wraps
from flask import request, jsonify
from pymongo import MongoClient
import re

# Check private IP utility
def is_private_ip(ip):
    private_ip_regex = re.compile(r'^((10\.)|(172\.1[6-9]\.)|(172\.2[0-9]\.)|(172\.3[0-1]\.)|(192\.168\.)|(127\.))')
    return private_ip_regex.match(ip) is not None

# Target validation decorator
def validate_target(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        target = request.json.get('target', '')
        if not target:
            return jsonify({'error': 'Target is required'}), 400

        last_part = target.split()[-1]
        localhost_regex = re.compile(r'^(localhost|127\.0\.0\.1)$')

        if is_private_ip(last_part) or localhost_regex.match(last_part):
            return jsonify({'error': 'Target must be a public IP or domain'}), 400

        return f(*args, **kwargs)
    return decorated_function

# Check for running scans decorator
def check_running_scan(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        userUID = kwargs.get('userUID')
        client = MongoClient()
        db = client["celery_nmap"]
        running_scan = db["currentRunningScan"].find_one({"userUID": userUID, "running": True})
        if running_scan:
            return jsonify({'error': 'A scan is already in progress for this user'}), 400
        return f(*args, **kwargs)
    return decorated_function
