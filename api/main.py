from flask import Flask, request, jsonify
import os
import uuid
import shutil

from google.cloud import cloudbuild_v1
from google.cloud import run_v2
from google.protobuf import duration_pb2
from google.api_core.exceptions import AlreadyExists

app = Flask(__name__)
PROJECT_ID = "projet-pipeline"
REGION = "europe-west1"

def trigger_build_and_deploy(full_id, site_path):
    image_uri = f"gcr.io/{PROJECT_ID}/{full_id}"

    # Initialisation client Cloud Build
    build_client = cloudbuild_v1.CloudBuildClient()

    # Configuration du build
    build = {
        "steps": [
            {
                "name": "gcr.io/cloud-builders/docker",
                "args": ["build", "-t", image_uri, "."],
                "dir": site_path
            },
            {
                "name": "gcr.io/cloud-builders/docker",
                "args": ["push", image_uri]
            }
        ],
        "images": [image_uri],
        "timeout": duration_pb2.Duration(seconds=600)
    }

    # Lancement du build
    build_op = build_client.create_build(project_id=PROJECT_ID, build=build)
    build_op.result()  # Attente de la fin du build

    # Initialisation client Cloud Run
    run_client = run_v2.ServicesClient()
    parent = f"projects/{PROJECT_ID}/locations/{REGION}"
    service_name = f"{parent}/services/{full_id}"

    container = run_v2.Container()
    container.image = image_uri
    container.ports = [{"containerPort": 8080}]

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

    # Dossier temporaire pour générer le Docker context
    site_path = f"/tmp/{full_id}"
    os.makedirs(site_path, exist_ok=True)

    # Écriture de index.html
    with open(os.path.join(site_path, "index.html"), "w") as f:
        f.write(html_code)

    # Dockerfile corrigé pour nginx sur PORT 8080
    dockerfile = """
FROM nginx:alpine

RUN rm /etc/nginx/conf.d/default.conf

RUN echo 'server {\\n\
    listen       ${PORT:-8080};\\n\
    server_name  localhost;\\n\
\\n\
    location / {\\n\
        root   /usr/share/nginx/html;\\n\
        index  index.html;\\n\
    }\\n\
}\\n' > /etc/nginx/conf.d/default.conf

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
