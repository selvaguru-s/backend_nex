import signal
import subprocess
from subprocess import PIPE
import re
from celery import Celery
import logging
from urllib.parse import quote_plus
from pymongo import MongoClient
import psutil
import time
import sys
from datetime import datetime, timezone

# Escape the username and password
username = 'selva'
password = 'Selva@12345'
escaped_username = quote_plus(username)
escaped_password = quote_plus(password)

# Initialize Celery with Redis as the broker
celery = Celery(
    __name__,
    broker='redis://localhost:7000/0'
)

# Initialize MongoDB client
try:
    mongo_client = MongoClient(f"mongodb+srv://{escaped_username}:{escaped_password}@cluster0.qtwmtf9.mongodb.net/")
    db = mongo_client['celery_nmap']
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    sys.exit(1)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@celery.task(name='tasks.tasks.perform_scan', queue='scan')
def perform_scan(target, userUID):
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
        collection = db[userUID]

        # Split the target and options
        parts = target.split(' ')
        target1 = parts[-1]
        options = parts[:-1]

        # Update task status to "STARTED" in the database
        collection.update_one({"task_id": perform_scan.request.id}, {"$set": {"status": "STARTED", "Target": target1, "Tool":"Nmap"}})

        # Build the command
        command = ['nmap'] + options + [target1]

        # Start the subprocess
        process = subprocess.Popen(command, stdout=PIPE, stderr=PIPE)

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
            logger.error("Nmap scan failed with error:\n%s", error)
            # Update task status to "FAILURE" in the database
            collection.update_one({"task_id": perform_scan.request.id}, {"$set": {"status": "FAILURE", "result": {"error": error}}})
            return {'error': error}

        logger.info("Nmap scan completed successfully")
        logger.debug("Nmap output:\n%s", output)

        # Update task status to "SUCCESS" in the database
        collection.update_one({"task_id": perform_scan.request.id}, {
            "$set": {
                "status": "SUCCESS",
               "Target": target1, 
               "Tool":"Nmap",
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
        collection.update_one({"task_id": perform_scan.request.id}, {"$set": {"status": "CANCELED", "result": {"error": "Scan was canceled by the user."}}})
        return {'error': "Scan was canceled by the user."}
    
    except Exception as e:
        logger.error("Error occurred during Nmap scan: %s", e)
        if collection:
            collection.update_one({"task_id": perform_scan.request.id}, {"$set": {"status": "FAILURE", "result": {"error": str(e)}}})
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


@celery.task(name='tasks.tasks.perform_network_tool',queue='basic')
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