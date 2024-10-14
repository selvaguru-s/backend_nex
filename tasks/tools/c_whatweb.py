
import signal
import subprocess
from subprocess import PIPE
import re
import logging
import psutil
import time
from tasks.celery_app import celery
from utils.mongo import db
from utils.user_scan_count import store_user_scancount_in_mongo 

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@celery.task(name='tasks.tasks.perform_whatweb',queue='whatweb')
def perform_whatweb(target, userUID=None):
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
        # Create a collection with the name as userUID if it doesn't exist
        collection = db[userUID]["whatweb"]

        # Update task status to "STARTED" in the database
        collection.update_one({"task_id": perform_whatweb.request.id}, {
            "$set": {
                "status": "STARTED",
                "Target": target,
                "Tool": "Whatweb"
            }
        })

        # Build the command
        command = ['whatweb', target]


        # Start the subprocess
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Get the psutil process object for the subprocess
        ps_process = psutil.Process(process.pid)

        # Initialize variables for CPU and memory usage
        cpu_usage = 0.0  # Total CPU usage over all samples
        memory_usage = 0.0  # Total memory usage over all samples
        sample_count = 0  # Number of samples taken

        # Monitor the process
        while True:
            # Check if the process is still running
            if process.poll() is not None:
                break
            
            # Sample CPU and memory usage
            cpu_usage += ps_process.cpu_percent(interval=0.1)  # Add the CPU usage since the last sample
            memory_info = ps_process.memory_info()
            memory_usage += memory_info.rss  # Add the current memory usage in bytes
            sample_count += 1  # Increment the sample count
            time.sleep(0.1)  # Adjust the sampling rate as needed

        # Wait for the process to complete and get the final output
        stdout, stderr = process.communicate()
        output = stdout.decode()
        error = stderr.decode()

        # Calculate average CPU and memory usage
        avg_cpu_usage = cpu_usage / sample_count if sample_count > 0 else 0.0
        avg_memory_usage = memory_usage / sample_count / (1024 * 1024) if sample_count > 0 else 0.0

        logger.info(f"Average CPU usage: {avg_cpu_usage:.2f}%")
        logger.info(f"Average memory usage: {avg_memory_usage:.2f} MB")

        # Remove escape sequences from the output
        pattern = re.compile(r'\x1b[^m]*m')
        output = re.sub(pattern, '', output)

        if process.returncode != 0:
            logger.error("WhatWeb scan failed with error:\n%s", error)
            # Update task status to "FAILURE" in the database
            collection.update_one({"task_id": perform_whatweb.request.id}, {
                "$set": {
                    "status": "FAILURE",
                    "result": {"error": error}
                }
            })
            return {'error': error}

        logger.info("WhatWeb scan completed successfully")
        logger.debug("WhatWeb output:\n%s", output)

        # Update task status to "SUCCESS" in the database
        collection.update_one({"task_id": perform_whatweb.request.id}, {
            "$set": {
                "status": "SUCCESS",
                "Target": target,
                "Tool":"Whatweb",
                "result": {
                    "output": output,
                    "avg_cpu_usage": avg_cpu_usage,
                    "avg_memory_usage": avg_memory_usage
                }
                
            }
        })

       
        store_user_scancount_in_mongo(userUID)

        return {'output': output, 'avg_cpu_usage': avg_cpu_usage, 'avg_memory_usage': avg_memory_usage}
    except KeyboardInterrupt:
        logger.info("Scan interrupted by user.")
        collection.update_one({"task_id": perform_whatweb.request.id}, {"$set": {"status": "CANCELED", "result": {"error": "Scan was canceled by the user."}}})
        return {'error': "Scan was canceled by the user."}
    except Exception as e:
        logger.error("Error occurred during WhatWeb scan: %s", e)
        if collection:
            collection.update_one({"task_id": perform_whatweb.request.id}, {
                "$set": {
                    "status": "FAILURE",
                    "result": {"error": str(e)}
                }
            })
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

