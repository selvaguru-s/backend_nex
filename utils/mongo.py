import pymongo
from urllib.parse import quote_plus

# Escape the username and password
username = 'selva'
password = 'Selva@12345'
escaped_username = quote_plus(username)
escaped_password = quote_plus(password)

# Connect to MongoDB Atlas
try:
    client = pymongo.MongoClient(f"mongodb+srv://{escaped_username}:{escaped_password}@cluster0.qtwmtf9.mongodb.net/")
    db = client["celery_nmap"]  # Replace 'celery_nmap' with your actual database name

    # Optional: Test the connection
    client.admin.command('ping')  # This will raise an exception if the connection fails
    print("Connected to MongoDB Atlas successfully!")

except pymongo.errors.ConnectionError as e:
    print(f"Failed to connect to MongoDB Atlas: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
