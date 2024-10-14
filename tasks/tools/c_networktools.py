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


@celery.task(name='tasks.tools.perform_network_tool',queue='basic')
def perform_network_tool(target, tool, userUID):
    collection = db[userUID]["basic"]
    current_scan = db['currentRunningScan']  # Define currentRunningScan upfront for the finally block


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
        # Define tool names and commands for each tool (mapped by tool number)
        tool_names = {
            '1': 'Ping',
            '2': 'WHOIS',
            '3': 'Traceroute',
            '4': 'DNS Lookup',
            '5': 'Reverse DNS',
            '6': 'SSL Checker'
        }

        commands = {
            '1': ['ping', '-c', '4', target],  # Ping tool
            '2': ['whois', target],            # WHOIS tool
            '3': ['traceroute', target],       # Traceroute tool
            '4': ['dig', target],              # DNS Lookup tool
            '5': ['dig', '-x', target],        # Reverse DNS tool
            '6': ['openssl', 's_client', '-connect', f'{target}:443']  # SSL Checker tool
        }

        # Get the command and tool name for the selected tool
        command = commands.get(str(tool))
        tool_name = tool_names.get(str(tool), 'Unknown Tool')

        if not command:
            logger.error("Invalid tool selection")
            collection.update_one({"task_id": perform_network_tool.request.id}, {"$set": {"status": "FAILURE", "result": {"error": "Invalid tool selected"}}})
            return {'error': 'Invalid tool selected'}

        # Update task status to "STARTED" in the database with the actual tool name
        collection.update_one(
            {"task_id": perform_network_tool.request.id},
            {"$set": {"status": "STARTED", "Target": target, "Tool": tool_name}}
        )

        # Start the subprocess to execute the command
        process = subprocess.Popen(command, stdout=PIPE, stderr=PIPE)

        # Get the psutil process object for resource monitoring
        ps_process = psutil.Process(process.pid)
        cpu_usage = 0.0
        memory_usage = 0.0
        sample_count = 0

        # Monitor the process for CPU and memory usage
        while True:
            if process.poll() is not None:
                break

            cpu_usage += ps_process.cpu_percent(interval=0.1)
            memory_usage += ps_process.memory_info().rss
            sample_count += 1
            time.sleep(0.1)

        # Wait for the process to complete
        stdout, stderr = process.communicate()
        output = stdout.decode()
        error = stderr.decode()

        avg_cpu_usage = cpu_usage / sample_count if sample_count > 0 else 0.0
        avg_memory_usage = memory_usage / sample_count / (1024 * 1024) if sample_count > 0 else 0.0

        if process.returncode != 0:
            logger.error(f"{command[0]} command failed with error:\n{error}")
            collection.update_one({"task_id": perform_network_tool.request.id}, {"$set": {"status": "FAILURE", "result": {"error": error}}})
            return {'error': error}

        # On success, update the task status to "SUCCESS"
        collection.update_one({"task_id": perform_network_tool.request.id}, {
            "$set": {
                "status": "SUCCESS",
                "Target": target,
                "Tool": tool_name,
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
        collection.update_one({"task_id": perform_network_tool.request.id}, {"$set": {"status": "CANCELED", "result": {"error": "Scan was canceled by the user."}}})
        return {'error': "Scan was canceled by the user."}
    
    except Exception as e:
        logger.error(f"Error occurred: {e}")
        collection.update_one({"task_id": perform_network_tool.request.id}, {"$set": {"status": "FAILURE", "result": {"error": str(e)}}})
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
