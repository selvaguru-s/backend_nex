import logging
from flask import Blueprint, jsonify, request
from auth.auth_decorator import token_required
from utils.cors_helpers import build_cors_preflight_response
from utils.decorators import check_running_scan, validate_target
from tasks.tasks import perform_whatweb
from utils.mongo import db 
import datetime
from datetime import datetime, timezone

whatweb_bp = Blueprint('whatweb', __name__)

@whatweb_bp.route('/whatweb', methods=['POST'])
@token_required
@validate_target
@check_running_scan
def whatweb(userUID=None):
    if request.method == 'OPTIONS':
        return build_cors_preflight_response()
    # Get the request payload
    data = request.json
    # Validate mandatory field "target"
    target = data.get('target')
    if not target:
        return jsonify({'error': 'Target field is required'}), 400
    

    try:
        # Dispatch Celery task with target and tool
        task = perform_whatweb.apply_async(args=[target,  userUID])
        task_id = task.id  # Store the task ID for later use

    # Get current date and time in UTC (aware)
        scan_datetime = datetime.now(timezone.utc)

        # Access collection for storing scan data
        collection = db[userUID]["whatweb"]   # Collection named after userUID
        collection2 = db['currentRunningScan']  # Separate collection for current running scans

        # Insert initial task status into the user-specific collection
        initial_status = {
            "task_id": task_id,
            "status": "Queued",
            "result": None,
            "Target": target,
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
        return jsonify({'message': 'Task has been initiated. Results will be available shortly.', 'task_id': task_id}), 202

    except Exception as e:
        logging.error(f"Error in whatweb route: {str(e)}")
        return jsonify({'error': str(e)}), 500