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
        ontology_url = os.environ.get('ONTOLOGY_URL', 'https://raw.githubusercontent.com/anpag/ontologies/main/src/application/henkel_demo.ttl')
        
        if not project_id:
            return jsonify({"error": "PROJECT_ID environment variable not set"}), 500

        print(f"Trigger received. Fetching ontology from {ontology_url}")
        
        # Download the file to a temporary location
        response = requests.get(ontology_url)
        response.raise_for_status()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ttl") as temp_file:
            temp_file.write(response.content)
            temp_file_path = temp_file.name

        print("Executing ontology ingestion and reasoning...")
        
        # Trigger the existing main.py logic
        ingest_ontology(temp_file_path, project_id, dataset_id)
        
        # Cleanup
        os.remove(temp_file_path)
        
        return jsonify({"status": "success", "message": "Ontology successfully staged to BigQuery."}), 200

    except Exception as e:
        print(f"Error during ingestion: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
