from functools import wraps
from flask import request, jsonify
from utils.mongo import db 
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

# Helper function to check current running scans for a user
def get_current_running_scan(userUID):
    try:
        collection = db["currentRunningScan"]
        query = {"userUID": userUID, "running": True}
        running_scan = collection.find_one(query)
        return running_scan  # Returns None if no running scan is found
    except Exception as e:
        raise Exception(f"Error fetching running scans: {str(e)}")


# Custom decorator to check for running scans
def check_running_scan(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        userUID = kwargs.get('userUID')  # Get userUID from the token_required decorator

        # Check if there is a running scan for this user
        running_scan = get_current_running_scan(userUID)

        if running_scan:
            return jsonify({'error': 'A scan is already in progress for this user'}), 400

        # Proceed if no running scan is found
        return f(*args, **kwargs)
    return decorated_function
    