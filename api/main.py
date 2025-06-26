from flask import Flask, request, jsonify
import os
import uuid
import shutil
import zipfile

from google.cloud import cloudbuild_v1
from google.cloud import run_v2
from google.cloud import storage
from google.protobuf import duration_pb2
from google.api_core.exceptions import AlreadyExists

app = Flask(__name__)

PROJECT_ID = "projet-pipeline"
REGION = "europe-west1"
BUCKET_NAME = "mon-bucket"  # <- Remplace par ton bucket GCS existant

def zip_dir(source_dir, output_filename):
    with zipfile.ZipFile(output_filename, 'w') as zipf:
        for root, _, files in os.walk(source_dir):
            for file in files:
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, source_dir)
                zipf.write(filepath, arcname=arcname)

def upload_to_gcs(bucket_name, source_file, destination_blob_name):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file)
    print(f"Uploaded {source_file} to gs://{bucket_name}/{destination_blob_name}")

def trigger_build_and_deploy(full_id, site_path):
    image_uri = f"gcr.io/{PROJECT_ID}/{full_id}"
    archive_path = f"/tmp/{full_id}.zip"
    object_name = f"source/{full_id}.zip"

    # Zip le dossier site_path
    zip_dir(site_path, archive_path)

    # Upload vers GCS
    upload_to_gcs(BUCKET_NAME, archive_path, object_name)

    build_client = cloudbuild_v1.CloudBuildClient()

    build = {
        "source": {
            "storage_source": {
                "bucket": BUCKET_NAME,
                "object": object_name
            }
        },
        "steps": [
            {
                "name": "gcr.io/cloud-builders/docker",
                "args": ["build", "-t", image_uri, "."]
            },
            {
                "name": "gcr.io/cloud-builders/docker",
                "args": ["push", image_uri]
            }
        ],
        "images": [image_uri],
        "timeout": duration_pb2.Duration(seconds=600)
    }

    # Démarre le build et attends la fin
    build_op = build_client.create_build(project_id=PROJECT_ID, build=build)
    build_op.result()

    # Déploiement Cloud Run
    run_client = run_v2.ServicesClient()
    parent = f"projects/{PROJECT_ID}/locations/{REGION}"
    service_name = f"{parent}/services/{full_id}"

    container = run_v2.Container()
    container.image = image_uri
    container.ports = [{"container_port": 8080}]

    template = run_v2.RevisionTemplate()
    template.containers = [container]

    service = run_v2.Service()
    service.name = service_name
    service.template = template

    try:
        run_client.create_service(parent=parent, service=service, service_id=full_id)
    except AlreadyExists:
        run_client.update_service(service=service)

    return f"https://{full_id}-{REGION}.a.run.app"

@app.route("/deploy", methods=["POST"])
def deploy():
    data = request.get_json()
    html_code = data.get("html")
    project_name = data.get("project_name", "site").replace(" ", "-").lower()
    site_id = str(uuid.uuid4())[:8]
    full_id = f"{project_name}-{site_id}"

    site_path = f"/tmp/{full_id}"
    os.makedirs(site_path, exist_ok=True)

    # Création index.html
    with open(os.path.join(site_path, "index.html"), "w") as f:
        f.write(html_code)

    # Création Dockerfile simple pour servir index.html via nginx
    dockerfile = """
    FROM nginx:alpine
    COPY index.html /usr/share/nginx/html/index.html
    """
    with open(os.path.join(site_path, "Dockerfile"), "w") as f:
        f.write(dockerfile.strip())

    try:
        url = trigger_build_and_deploy(full_id, site_path)
        return jsonify({
            "message": "Déploiement terminé",
            "site_id": full_id,
            "url": url
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        shutil.rmtree(site_path, ignore_errors=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
