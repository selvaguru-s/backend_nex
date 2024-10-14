from functools import wraps
from flask import request, jsonify
from firebase_admin import auth
from firebase_admin._auth_utils import InvalidIdTokenError
from utils.helpers import verify_id_token

def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                id_token = auth_header.split('Bearer ')[1]
            else:
                return jsonify({'error': 'Invalid authorization header'}), 401

            decoded_token = verify_id_token(id_token)
            userUID = decoded_token.get('user_id')
            if not userUID:
                return jsonify({'error': 'Invalid token, user_id not found'}), 401

            kwargs['userUID'] = userUID
        except InvalidIdTokenError:
            return jsonify({'error': 'Invalid ID token'}), 401
        except Exception as e:
            return jsonify({'error': str(e)}), 401

        return f(*args, **kwargs)
    return decorated_function
