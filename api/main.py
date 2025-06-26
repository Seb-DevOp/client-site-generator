from flask import Flask, request, jsonify
import os
import uuid
import shutil
import tempfile
from google.cloud import storage, cloudbuild_v1
from google.protobuf import duration_pb2

app = Flask(__name__)

PROJECT_ID = "projet-pipeline"
BUCKET_NAME = "projet-pipeline-build-context"  # Doit exister

def upload_to_gcs(local_path, gcs_path):
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)

    for root, _, files in os.walk(local_path):
        for file in files:
            local_file_path = os.path.join(root, file)
            relative_path = os.path.relpath(local_file_path, local_path)
            blob = bucket.blob(f"{gcs_path}/{relative_path}")
            blob.upload_from_filename(local_file_path)

def trigger_cloud_build(full_id, gcs_path):
    client = cloudbuild_v1.CloudBuildClient()

    build = {
        "source": {
            "storage_source": {
                "bucket": BUCKET_NAME,
                "object": f"{gcs_path}/"
            }
        },
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
        "timeout": duration_pb2.Duration(seconds=600),
        "images": [f"gcr.io/{PROJECT_ID}/{full_id}"]
    }

    operation = client.create_build(project_id=PROJECT_ID, build=build)
    return operation.result()

@app.route("/deploy", methods=["POST"])
def deploy():
    data = request.get_json()
    html_code = data["html"]
    project_name = data["project_name"].replace(" ", "-").lower()
    site_id = str(uuid.uuid4())[:8]
    full_id = f"{project_name}-{site_id}"
    gcs_path = f"build-contexts/{full_id}"

    with tempfile.TemporaryDirectory() as temp_dir:
        # Crée un index.html
        os.makedirs(os.path.join(temp_dir, "app"), exist_ok=True)
        with open(os.path.join(temp_dir, "app/index.html"), "w") as f:
            f.write(html_code)

        # Copie un Dockerfile "générique"
        shutil.copy("docker/Dockerfile", os.path.join(temp_dir, "Dockerfile"))

        # Upload dans GCS
        upload_to_gcs(temp_dir, gcs_path)

    # Lance le build
    result = trigger_cloud_build(full_id, gcs_path)

    return jsonify({"message": "Déploiement lancé", "site_id": full_id, "build_status": result.status.name})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
