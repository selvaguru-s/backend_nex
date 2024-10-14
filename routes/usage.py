from flask import Blueprint, jsonify
from auth.auth_decorator import token_required
from utils.mongo import db 

usage_bp = Blueprint('usage', __name__)


@usage_bp.route('/total_usage', methods=['GET'])
@token_required
def total_usage(userUID=None):
    results = []
    # Fetch data from the specified collection
    user_collection = db[userUID]['total_usage']  # Access collection based on userUID
    for result in user_collection.find():
        # Exclude '_id' field from the response
        result.pop('_id')
        results.append(result)
    return jsonify(results)

@usage_bp.route('/daily_usage', methods=['GET'])
@token_required
def daily_usage(userUID=None):
    results = []
    # Fetch data from the specified collection
    user_collection = db[userUID]['daily_usage']  # Access collection based on userUID
    for result in user_collection.find():
        # Exclude '_id' field from the response
        result.pop('_id')
        results.append(result)
    return jsonify(results)

# Route to fetch data from MongoDB collection
@usage_bp.route('/count', methods=['GET'])
@token_required
def count(userUID=None):
    results = []
    # Fetch data from the specified collection
    user_collection = db[userUID]['user_request_counts']  # Access collection based on userUID
    for result in user_collection.find():
        # Exclude '_id' field from the response
        result.pop('_id')
        results.append(result)
    return jsonify(results)
