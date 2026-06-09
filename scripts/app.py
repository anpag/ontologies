import os
import tempfile
from flask import Flask, request, jsonify
from main import ingest_ontology
import requests

app = Flask(__name__)

@app.route('/', methods=['POST'])
def handle_event():
    """
    Handles the incoming webhook or Eventarc payload.
    In a full production setup, this would parse the GitHub/Eventarc payload 
    to find the specific .ttl file that changed. For this demo, we will 
    fetch the demo file from the repository and trigger ingestion.
    """
    try:
        # Extract configuration from environment variables
        project_id = os.environ.get('PROJECT_ID')
        dataset_id = os.environ.get('DATASET_ID', 'kg_ontology_staging')
        # Default to main branch, but override if we get a specific ref/tag from the webhook
        branch_or_tag = "main"
        
        # Extract payload from Eventarc/PubSub envelope
        envelope = request.get_json()
        version_info = "Unknown Version"
        
        if envelope and isinstance(envelope, dict) and "message" in envelope:
            pubsub_message = envelope["message"]
            if isinstance(pubsub_message, dict) and "data" in pubsub_message:
                try:
                    data_str = base64.b64decode(pubsub_message["data"]).decode("utf-8").strip()
                    data_json = json.loads(data_str)
                    
                    # If this was triggered by a tag push, the ref will look like refs/tags/v1.0.0
                    # If it was a branch, it looks like refs/heads/main
                    ref = data_json.get("ref", "")
                    if ref.startswith("refs/tags/"):
                        branch_or_tag = ref.replace("refs/tags/", "")
                        version_info = branch_or_tag # Use the tag name (e.g., v1.0.0) as the version!
                    else:
                        version_info = data_json.get("commit_sha", "Unknown Version")
                        
                    print(f"Extracted version info: {version_info}, branch/tag: {branch_or_tag}")
                except Exception as e:
                    print(f"Could not parse payload as JSON: {e}")

        # Construct the raw GitHub URL dynamically pointing to the exact tag or branch
        ontology_url = f"https://raw.githubusercontent.com/anpag/ontologies/{branch_or_tag}/src/application/henkel_demo.ttl"
        
        if not project_id:
            return jsonify({"error": "PROJECT_ID environment variable not set"}), 500

        import base64
        import json

        # Extract payload from Eventarc/PubSub envelope
        envelope = request.get_json()
        version_info = "Unknown Version"
        
        if envelope and isinstance(envelope, dict) and "message" in envelope:
            pubsub_message = envelope["message"]
            if isinstance(pubsub_message, dict) and "data" in pubsub_message:
                try:
                    data_str = base64.b64decode(pubsub_message["data"]).decode("utf-8").strip()
                    data_json = json.loads(data_str)
                    version_info = data_json.get("commit_sha", "Unknown Version")
                    print(f"Extracted version info: {version_info}")
                except Exception as e:
                    print(f"Could not parse payload as JSON: {e}")

        print(f"Trigger received. Fetching ontology from {ontology_url}")
        
        # Download the file to a temporary location
        response = requests.get(ontology_url)
        response.raise_for_status()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ttl") as temp_file:
            temp_file.write(response.content)
            temp_file_path = temp_file.name

        print("Executing ontology ingestion and reasoning...")
        
        # Trigger the existing main.py logic
        ingest_ontology(temp_file_path, project_id, dataset_id, version_info)
        
        # Cleanup
        os.remove(temp_file_path)
        
        return jsonify({"status": "success", "message": "Ontology successfully staged to BigQuery."}), 200

    except Exception as e:
        print(f"Error during ingestion: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
