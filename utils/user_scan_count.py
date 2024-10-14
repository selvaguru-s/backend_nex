from utils.mongo import db 
import logging

# Setup logger
logger = logging.getLogger(__name__)


def store_user_scancount_in_mongo(userUID):
    try:
        # Increment request count for the user
        db[userUID]['user_request_counts'].update_one(
            {'userUID': userUID},
            {'$inc': {'request_count': 1}},
            upsert=True
        )
    except Exception as e:
        logger.error(f"Error storing result in MongoDB: {e}")