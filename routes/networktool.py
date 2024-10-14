from datetime import timezone
import datetime
from flask import Blueprint, jsonify, request
from auth.auth_decorator import token_required
from utils.cors_helpers import build_cors_preflight_response
from utils.decorators import validate_target
from tasks.tasks import perform_network_tool
from utils.mongo import db 

networktool_bp = Blueprint('networktool', __name__)

@networktool_bp.route('/networktool', methods=['POST'])
@token_required
@validate_target
def networktool(userUID=None):
    if request.method == 'OPTIONS':
        return build_cors_preflight_response()
    data = request.get_json()
    target = data.get('target')
    tool = data.get('tool')
    
    # Validate input
    if not target or not tool:
        return jsonify({'error': 'Target and tool are required'}), 400
    
    try:
        # Dispatch Celery task with target and tool
        task = perform_network_tool.apply_async(args=[target, tool, userUID])
        task_id = task.id  # Store the task ID for later use

        # Get current date and time in UTC (aware)
        scan_datetime = datetime.now(timezone.utc)

        # Access collection for storing scan data
        collection = db[userUID]["basic"]   # Collection named after userUID
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
        return jsonify({'error': str(e)}), 500
    