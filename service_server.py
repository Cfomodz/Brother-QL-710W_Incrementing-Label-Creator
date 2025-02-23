from flask import Flask, request, jsonify
import subprocess
import threading
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Function to run your script
def run_script():
    # Get paths from .env
    python_path = os.getenv('PYTHON_PATH', 'python3')
    service_path = os.getenv('SERVICE_PATH', 'whatnot_live_label_writer.py')
    
    # Run the print server
    subprocess.run([python_path, service_path])

@app.route('/start-service', methods=['POST'])
def start_service():
    # Run the script in a separate thread to avoid blocking the main thread
    thread = threading.Thread(target=run_script)
    thread.start()
    return jsonify({"status": "Service started"}), 200

if __name__ == '__main__':
    # Run the Flask app on all available IPs (0.0.0.0) and a different port
    app.run(host='0.0.0.0', port=5001)