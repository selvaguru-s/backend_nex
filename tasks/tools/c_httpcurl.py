import signal
import subprocess
from subprocess import PIPE
import re
import logging
import psutil
import time
import base64
from pymongo import MongoClient
from tasks.celery_app import celery
from utils.user_scan_count import store_user_scancount_in_mongo

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@celery.task(name='tasks.tasks.c_httpcurl.perform_httpcurl', queue='httpcurl')
def perform_httpcurl(data, userUID=None):
    # Initialize the MongoDB client here
    mongo_client = MongoClient('your_connection_string')  # Replace with your MongoDB connection string
    db = mongo_client['your_database_name']  # Replace with your database name
    collection = None
    current_scan = db['currentRunningScan']

    def cleanup(signum, frame):
        current_scan.update_one(
            {"userUID": userUID, "running": True},
            {
                "$set": {
                    "running": False
                }
            }
        )
        raise KeyboardInterrupt  # Raise an exception to break the scan loop

    # Register the cleanup function for SIGINT (Ctrl+C) and SIGTERM
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        target = data.get('target')
        method = data.get('method', 'GET')
        body = data.get('body', '')
        auth_type = data.get('authType', 'No Auth')
        bearer_token = data.get('bearerToken', '')
        username = data.get('username', '')
        password = data.get('password', '')
        token_type = data.get('tokenType', '')
        custom_credentials = data.get('customCredentials', '')
        headers = data.get('headers', {})

        # Create a collection with the name as userUID if it doesn't exist
        collection = db[userUID]["httpcurl"]

        # Update task status to "STARTED" in the database
        collection.update_one({"task_id": perform_httpcurl.request.id}, {
            "$set": {
                "status": "STARTED",
                "Target": target,
                "Tool": "Curl"
            }
        })

        # Prepare the curl command for the body
        curl_command_body = ['curl', '-s', '-L', '-I', '-X', method, target]  # '-s' for silent mode, '-L' to follow redirects

        # Handle Authorization header based on selected type
        if auth_type == 'Bearer':
            if not bearer_token:
                return {'error': 'Bearer token is required'}
            curl_command_body.append(f'--header=Authorization: Bearer {bearer_token}')
        elif auth_type == 'Basic':
            if not username or not password:
                return {'error': 'Username and password are required for Basic Auth'}
            encoded_credentials = f"{username}:{password}".encode('utf-8')
            curl_command_body.append(f'--header=Authorization: Basic {base64.b64encode(encoded_credentials).decode()}')
        elif auth_type == 'Custom':
            if not token_type or not custom_credentials:
                return {'error': 'Token Type and Credentials are required for Custom Auth'}
            curl_command_body.append(f'--header=Authorization: {token_type} {custom_credentials}')

        # Add headers to the curl command
        for key, value in headers.items():
            curl_command_body.append(f'--header={key}: {value}')

        # Add body if present (only applies to POST, PUT, etc.)
        if body and method in ['POST', 'PUT', 'PATCH']:
            curl_command_body.append(f'--data={body}')

        # Start the subprocess
        process = subprocess.Popen(curl_command_body, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Get the psutil process object for the command
        ps_process = psutil.Process(process.pid)

        # Initialize variables for CPU and memory usage
        cpu_usage = 0.0  # Total CPU usage over all samples
        memory_usage = 0.0  # Total memory usage over all samples
        sample_count = 0  # Number of samples taken

        # Monitor the process
        while True:
            if process.poll() is not None:
                break

            # Sample CPU and memory usage
            cpu_usage += ps_process.cpu_percent(interval=0.1)
            memory_info = ps_process.memory_info()
            memory_usage += memory_info.rss  # Memory usage in bytes
            sample_count += 1
            time.sleep(0.1)

        # Get final output for both processes
        stdout, stderr = process.communicate()
        output_body = stdout.decode()
        error_body = stderr.decode()

        # Calculate average CPU and memory usage
        avg_cpu_usage = cpu_usage / sample_count if sample_count > 0 else 0.0
        avg_memory_usage = memory_usage / sample_count / (1024 * 1024) if sample_count > 0 else 0.0

        logger.info(f"Average CPU usage: {avg_cpu_usage:.2f}%")
        logger.info(f"Average memory usage: {avg_memory_usage:.2f} MB")

        # Remove escape sequences from the outputs
        output_body = re.sub(r'\x1b[^m]*m', '', output_body)

        print(output_body)
     

        # Store the results for both body and headers in the database
        # Treat all responses as success for logging purposes
        logger.info("Curl body and headers commands completed successfully")

        # Update task status to "SUCCESS" in the database
        collection.update_one({"task_id": perform_httpcurl.request.id}, {
            "$set": {
                "status": "SUCCESS",
                "Target": target,
                "Tool": "Curl",
                "result": {
                    "output": output_body,

                    "avg_cpu_usage": avg_cpu_usage,
                    "avg_memory_usage": avg_memory_usage
                }
            }
        })

        # Update user scan count
        store_user_scancount_in_mongo(userUID)



    except KeyboardInterrupt:
        logger.info("Scan interrupted by user.")
        collection.update_one({"task_id": perform_httpcurl.request.id}, {
            "$set": {
                "status": "CANCELED",
                "result": {"error": "Scan was canceled by the user."}
            }
        })
        return {'error': "Scan was canceled by the user."}

    except Exception as e:
        logger.error(f"Error occurred during the Curl scan: {e}")
        if collection:
            collection.update_one({"task_id": perform_httpcurl.request.id}, {
                "$set": {
                    "status": "FAILURE",
                    "result": {"error": str(e)}
                }
            })
        return {'error': str(e)}

    finally:
        # Ensure running is set to False no matter what happens
        current_scan.update_one(
            {"userUID": userUID, "running": True},
            {
                "$set": {
                    "running": False
                }
            }
        )
