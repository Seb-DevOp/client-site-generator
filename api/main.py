from flask import Flask, request, jsonify
import os
import uuid
from google.cloud.devtools import cloudbuild_v1
from google.protobuf import duration_pb2

app = Flask(__name__)

PROJECT_ID = os.environ.get("PROJECT_ID", "projet-pipeline")  # safer

def trigger_build(full_id):
    client = cloudbuild_v1.CloudBuildClient()

    build = {
        "steps": [
            {
                "name": "gcr.io/cloud-builders/docker",
                "args": ["build", "-t", f"gcr.io/{PROJECT_ID}/{full_id}", "."]
            },
            {
                "name": "gcr.io/cloud-builders/docker",
                "args": ["push", f"gcr.io/{PROJECT_ID}/{full_id}"]
            }
        ],
        "timeout": duration_pb2.Duration(seconds=600)
    }

    operation = client.create_build(project_id=PROJECT_ID, build=build)
    result = operation.result()
    return result

@app.route("/deploy", methods=["POST"])
def deploy():
    try:
        data = request.get_json()
        html_code = data["html"]
        project_name = data["project_name"].replace(" ", "-").lower()
        site_id = str(uuid.uuid4())[:8]
        full_id = f"{project_name}-{site_id}"

        site_dir = f"/tmp/sites/{full_id}"
        os.makedirs(site_dir, exist_ok=True)

        with open(os.path.join(site_dir, "index.html"), "w") as f:
            f.write(html_code)

        build_result = trigger_build(full_id)

        return jsonify({
            "message": "Déploiement lancé",
            "site_id": full_id,
            "build_result": str(build_result)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def root():
    return "Site deployer API is up"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
