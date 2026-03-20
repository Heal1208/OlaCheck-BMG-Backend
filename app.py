import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify
from flask_cors import CORS
from database import init_seed
from routes.auth     import auth_bp
from routes.stores   import stores_bp
from routes.admin    import admin_bp
from routes.checkins import checkins_bp

app = Flask(__name__)
CORS(app)

app.register_blueprint(auth_bp)
app.register_blueprint(stores_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(checkins_bp)

@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "message": "Endpoint not found."}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"success": False, "message": "Method not allowed."}), 405

@app.errorhandler(500)
def internal_error(e):
    return jsonify({"success": False, "message": "Internal server error."}), 500

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"success": True, "message": "BMG Smart Retail API is running."}), 200

if __name__ == "__main__":
    init_seed()
    app.run(debug=True, host="0.0.0.0", port=5000)