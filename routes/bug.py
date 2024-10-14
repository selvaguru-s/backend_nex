from flask import Blueprint, jsonify, request
from auth.auth_decorator import token_required
import re
from utils.mongo import db 
from utils.cors_helpers import build_cors_preflight_response

bug_bp = Blueprint('bug', __name__)

@bug_bp.route('/report-bug', methods=['POST'])
@token_required
def report_bug(userUID):
    if request.method == 'OPTIONS':
        return build_cors_preflight_response()
    
    def sanitize_input(value):
        """Sanitize input by removing HTML tags and escaping special characters."""
        return re.sub(r'<.*?>', '', value)  # Removes HTML tags
    bug_type = request.json.get('bugType')
    description = request.json.get('description')

    if not bug_type or not description:
        return jsonify({'error': 'Missing bugType or description'}), 400
    
    # Sanitize inputs
    bug_type2 = sanitize_input(bug_type)
    description2 = sanitize_input(description)

    # Get the latest issue number from the database
    user_collection = db['bug_tracking']
    latest_bug = user_collection.find_one(sort=[("issue_number", -1)])

    if latest_bug:
        last_issue_number = int(latest_bug['issue_number'][1:])  # Extract number after '#'
        next_issue_number = f"#{last_issue_number + 1}"
    else:
        next_issue_number = "#1000"  # Start from #1000 if no bugs exist

    bug_report = {
        'user_id': userUID,
        'bug_type': bug_type2,
        'description': description2,
        'issue_number': next_issue_number,
        'status': 'Not_Fixed'

    }

    # Store the bug report in the user's collection
    user_collection.insert_one(bug_report)

    return jsonify({'message': 'Bug report submitted successfully', 'issue_number': next_issue_number}), 200


@bug_bp.route('/fetch_fbug', methods=['GET'])
@token_required
def get_bug_reports(userUID):
    # Get bug reports with status='Fixed' from the database
    user_collection = db['bug_tracking']
    bug_reports = list(user_collection.find({'status': 'Fixed'}))

    # Convert ObjectId to string and format issue_number for response
    for bug in bug_reports:
        bug['_id'] = str(bug['_id'])  # Convert ObjectId to string
        bug['issue_number'] = bug['issue_number']  # Keep issue_number as is

    return jsonify(bug_reports), 200