from firebase_admin import auth
from firebase_admin._auth_utils import InvalidIdTokenError

def verify_id_token(id_token):
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except (ValueError, InvalidIdTokenError) as e:
        raise e
