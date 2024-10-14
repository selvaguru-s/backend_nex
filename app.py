from flask import Flask
from flask_cors import CORS
from auth.firebase import init_firebase
from routes.scan import scan_bp
from routes.networktool import networktool_bp
from routes.whatweb import whatweb_bp
from routes.sublist3r import sublist3r_bp
from routes.usage import usage_bp
from routes.bug import bug_bp
from routes.result_fetch import result_dp
import logging

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["https://nexusbot-connect.web.app", "https://nexusbot.app"]}})

# Initialize Firebase Admin SDK
init_firebase()

# Register blueprints for routes
app.register_blueprint(scan_bp)
app.register_blueprint(networktool_bp)
app.register_blueprint(whatweb_bp)
app.register_blueprint(sublist3r_bp)
app.register_blueprint(usage_bp)
app.register_blueprint(bug_bp)
app.register_blueprint(result_dp)

if __name__ == "__main__":
    app.run(debug=True)
