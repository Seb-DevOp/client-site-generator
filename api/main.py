from flask import Flask, request, jsonify
import os
import uuid
from google.cloud import cloudbuild_v1
from google.protobuf import duration_pb2

app = Flask(__name__)

def trigger_build(full_id):
    client = cloudbuild_v1.CloudBuildClient()
    project_id = "projet-pipeline"

    build = {
        "steps": [
            {
                "name": "gcr.io/cloud-builders/docker",
                "args": ["build", "-t", f"gcr.io/{project_id}/{full_id}", "."]
            },
            {
                "name": "gcr.io/cloud-builders/docker",
                "args": ["push", f"gcr.io/{project_id}/{full_id}"]
            }
        ],
        "timeout": duration_pb2.Duration(seconds=600)
    }

    operation = client.create_build(project_id=project_id, build=build)
    result = operation.result()
    return result

@app.route("/deploy", methods=["POST"])
def deploy():
    data = request.get_json()
    html_code = data["html"]
    project_name = data["project_name"].replace(" ", "-").lower()
    site_id = str(uuid.uuid4())[:8]
    full_id = f"{project_name}-{site_id}"

    # Créer dossier temporaire avec HTML
    os.makedirs(f"./sites/{full_id}", exist_ok=True)
    with open(f"./sites/{full_id}/index.html", "w") as f:
        f.write(html_code)

    # Déclenchement du build via l’API
    build_result = trigger_build(full_id)

    return jsonify({"message": "Déploiement lancé", "site_id": full_id, "build_result": str(build_result)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
