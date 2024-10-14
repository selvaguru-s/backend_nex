from flask import Blueprint, jsonify, request
from auth.auth_decorator import token_required
from utils.cors_helpers import build_cors_preflight_response
from utils.decorators import validate_target, check_running_scan
from tasks.tasks import perform_scan
import datetime
from datetime import datetime, timezone
from utils.mongo import db 

scan_bp = Blueprint('scan', __name__)

@scan_bp.route('/scan', methods=['POST'])
@token_required
@validate_target
@check_running_scan
def scan(userUID=None):
    if request.method == 'OPTIONS':
        return build_cors_preflight_response()
    target = request.json['target']
    # Trigger Celery task
    result = perform_scan.apply_async(args=[target, userUID])
    task_id = result.id

    # Split the target and options
    parts = target.split(' ')
    target1 = parts[-1]
    options = parts[:-1]
    # Inside your scan route

 # Get current date and time in UTC (aware)
    scan_datetime = datetime.now(timezone.utc)

    # Access collection for storing scan data
    collection = db[userUID]  # Collection named after userUID
    collection2 = db['currentRunningScan']  # Separate collection for current running scans

    # Insert initial task status into the user-specific collection
    initial_status = {
        "task_id": task_id,
        "status": "Queued",
        "result": None,
        "Target": target1,
        "traceback": None,
        "scan_datetime": scan_datetime,
        "userUID": userUID  # Adding userUID to the document
    }
    collection.insert_one(initial_status)

    # Update or insert document in 'currentRunningScan' collection to track running scans
    collection2.update_one(
        {"userUID": userUID},  # Find the document where userUID matches
        {"$set": {"running": True}},  # Set 'running' to True
        upsert=True  # Insert a new document if no match is found
    )


    # Respond to the API request immediately
    return jsonify({'message': 'Task has been initiated. Results will be available shortly.', 'task_id': task_id})
