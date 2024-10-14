from flask import Blueprint, jsonify
from auth.auth_decorator import token_required
from utils.mongo import db 

result_dp = Blueprint('usage', __name__)

@result_dp.route('/results', methods=['GET'])
@token_required
def get_results(userUID=None):
    results = []
    
    # Fetch data from the specified collections
    user_collection = db[userUID]
    user_collection2 = db[userUID]["basic"]  # Access collection based on userUID
    user_collection3 = db[userUID]["whatweb"] 
    user_collection4 = db[userUID]["sublist3r"] 
    # Fetch data from the first collection
    for result in user_collection.find():
        # Exclude '_id' field from the response
        result.pop('_id')
        results.append(result)

    # Fetch data from the second collection
    for result in user_collection2.find():
        # Exclude '_id' field from the response
        result.pop('_id')
        results.append(result)

    # Fetch data from the second collection
    for result in user_collection3.find():
        # Exclude '_id' field from the response
        result.pop('_id')
        results.append(result)
    # Fetch data from the second collection
    for result in user_collection4.find():
        # Exclude '_id' field from the response
        result.pop('_id')
        results.append(result)

    return jsonify(results)
