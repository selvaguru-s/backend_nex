from firebase_admin import credentials, initialize_app

def init_firebase():
    try:
        cred = credentials.Certificate("serviceAccountKey.json")
        initialize_app(cred)
    except FileNotFoundError:
        print("Error: serviceAccountKey.json not found.")
