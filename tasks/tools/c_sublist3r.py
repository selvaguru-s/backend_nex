
import signal
import subprocess
from subprocess import PIPE
import re
import logging
import psutil
import time
from celery_app import celery
from utils.mongo import db
from utils.user_scan_count import store_user_scancount_in_mongo 

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@celery.task(name='tasks.tasks.perform_sublist3r',queue='sublist3r')
def perform_sublist3r(data, userUID=None):
    collection = None
    current_scan = db['currentRunningScan']
    
    try:
        # Create a collection with the name as userUID if it doesn't exist
        collection = db[userUID]["sublist3r"]

        target = data.get('target')
        # Update task status to "STARTED" in the database
        collection.update_one(
            {"task_id": perform_sublist3r.request.id}, 
            {
                "$set": {
                    "status": "STARTED",
                    "Target": target,
                    "Tool": "sublist3r"
                }
            }
        )

        # Build the sublist3r command with optional parameters
        command = ['sublist3r', '-d', target]


        # Start the subprocess for sublist3r
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Get the psutil process object for the subprocess
        ps_process = psutil.Process(process.pid)

        # Initialize variables for CPU and memory usage
        cpu_usage = 0.0
        memory_usage = 0.0
        sample_count = 0

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

        # Wait for the process to complete and get the final output
        stdout, stderr = process.communicate()
        output = stdout.decode()
        error = stderr.decode()

        # Calculate average CPU and memory usage
        avg_cpu_usage = cpu_usage / sample_count if sample_count > 0 else 0.0
        avg_memory_usage = memory_usage / sample_count / (1024 * 1024) if sample_count > 0 else 0.0

        logger.info(f"Average CPU usage: {avg_cpu_usage:.2f}%")
        logger.info(f"Average memory usage: {avg_memory_usage:.2f} MB")

        # Clean output by removing any escape sequences
        pattern = re.compile(r'\x1b[^m]*m')
        output = re.sub(pattern, '', output)

        if process.returncode != 0:
            logger.error("Sublist3r scan failed with error:\n%s", error)
            # Update task status to "FAILURE" in the database
            collection.update_one(
                {"task_id": perform_sublist3r.request.id}, 
                {
                    "$set": {
                        "status": "FAILURE",
                        "result": {"error": error}
                    }
                }
            )
            return {'error': error}

        logger.info("Sublist3r scan completed successfully")
        logger.debug("Sublist3r output:\n%s", output)

        # Update task status to "SUCCESS" in the database
        collection.update_one(
            {"task_id": perform_sublist3r.request.id}, 
            {
                "$set": {
                    "status": "SUCCESS",
                    "Target": target,
                    "Tool": "sublist3r",
                    "result": {
                        "output": output,
                        "avg_cpu_usage": avg_cpu_usage,
                        "avg_memory_usage": avg_memory_usage
                    }
                }
            }
        )

        # Update the user's scan count in MongoDB
        store_user_scancount_in_mongo(userUID)

        return {'output': output, 'avg_cpu_usage': avg_cpu_usage, 'avg_memory_usage': avg_memory_usage}
    except KeyboardInterrupt:
        logger.info("Scan interrupted by user.")
        collection.update_one({"task_id": perform_sublist3r.request.id}, {"$set": {"status": "CANCELED", "result": {"error": "Scan was canceled by the user."}}})
        return {'error': "Scan was canceled by the user."}
    except Exception as e:
        logger.error("Error occurred during Sublist3r scan: %s", e)
        if collection:
            collection.update_one(
                {"task_id": perform_sublist3r.request.id}, 
                {
                    "$set": {
                        "status": "FAILURE",
                        "result": {"error": str(e)}
                    }
                }
            )
        return {'error': str(e)}

    finally:
        # Ensure running is set to False no matter what happens
        current_scan.update_one(
            {"userUID": userUID, "running": True},  # Match the running scan for this user
            {
                "$set": {
                    "running": False
                }
            }
        )