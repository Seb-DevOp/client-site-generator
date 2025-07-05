from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import os
import uuid
import shutil
import threading
import traceback
from google.cloud.devtools import cloudbuild_v1
from google.cloud import storage
import sys
import subprocess
import google.auth
import tarfile
from googleapiclient import discovery
from google.oauth2 import service_account

app = FastAPI()
PROJECT_ID = "projet-pipeline"
REGION = "europe-west1"
BUCKET_NAME = "site-deploy"

# Stockage en mémoire de l'état des builds (pour démo)
build_status = {}

print("PYTHONPATH:", sys.path)
print("THREAD sys.path:", sys.path)
print("==== PIP FREEZE (au boot) ====")
print(subprocess.getoutput('pip freeze'))

try:
    print("cloudbuild_v1 est bien importé !")
except ImportError as e:
    print("ERREUR IMPORT cloudbuild_v1 :", e)
    raise

def prepare_site_files(project, html):
    site_id = str(uuid.uuid4())[:8]
    safe_project = project.replace(" ", "-").lower()
    full_id = f"{safe_project}-{site_id}"
    site_path = f"/tmp/{full_id}"
    os.makedirs(site_path, exist_ok=True)
    with open(os.path.join(site_path, "index.html"), "w") as f:
        f.write(html)
    # Générer la config Nginx pour écouter sur 8080
    nginx_conf = '''
events {}
http {
    server {
        listen 8080;
        location / {
            root /usr/share/nginx/html;
            index index.html;
        }
    }
}
'''
    with open(os.path.join(site_path, "nginx.conf"), "w") as f:
        f.write(nginx_conf)
    # Dockerfile compatible Cloud Run
    dockerfile_content = """
    FROM nginx:alpine
    COPY index.html /usr/share/nginx/html/index.html
    COPY nginx.conf /etc/nginx/nginx.conf
    EXPOSE 8080
    CMD ["nginx", "-g", "daemon off;", "-c", "/etc/nginx/nginx.conf"]
    """
    with open(os.path.join(site_path, "Dockerfile"), "w") as f:
        f.write(dockerfile_content.strip())
    return full_id, site_path

def upload_to_gcs(local_file, bucket_name, gcs_path):
    print(f"Upload {local_file} -> gs://{bucket_name}/{gcs_path}")
    try:
        credentials, project = google.auth.default()
        client = storage.Client(credentials=credentials, project=project)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(gcs_path)
        blob.upload_from_filename(local_file)
        print("Upload terminé !")
    except Exception as e:
        print(f"Erreur lors de l'upload GCS : {e}")
        raise

def make_tarfile(output_filename, source_dir):
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir, arcname=".")

def trigger_build(full_id, site_path, project_id):
    from google.protobuf import duration_pb2
    image_uri = f"gcr.io/{project_id}/{full_id}"
    build_client = cloudbuild_v1.CloudBuildClient()
    # 1. Archive le contexte
    tar_path = f"/tmp/{full_id}.tar.gz"
    make_tarfile(tar_path, site_path)
    # 2. Upload sur GCS
    gcs_tar_path = f"build-contexts/{full_id}.tar.gz"
    upload_to_gcs(tar_path, BUCKET_NAME, gcs_tar_path)
    # 3. Définition du build
    build = {
        "source": {
            "storage_source": {
                "bucket": BUCKET_NAME,
                "object_": gcs_tar_path
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
    build_op = build_client.create_build(project_id=project_id, build=build)
    build_op.result()
    return image_uri

def deploy_to_cloud_run(full_id, image_uri, project_id, region):
    from google.cloud import run_v2
    from google.cloud.run_v2.types import Service, RevisionTemplate, Container, ContainerPort, ResourceRequirements
    from google.protobuf.duration_pb2 import Duration
    from google.api_core.exceptions import AlreadyExists
    client = run_v2.ServicesClient()
    parent = f"projects/{project_id}/locations/{region}"
    service_id = full_id
    service_name = f"{parent}/services/{service_id}"
    container = Container()
    container.image = image_uri
    container.ports.append(ContainerPort(container_port=8080))
    container.resources = ResourceRequirements(
        limits={"memory": "1Gi", "cpu": "2"}
    )
    template = RevisionTemplate()
    template.containers = [container]
    template.timeout = Duration(seconds=300)
    service = Service()
    service.template = template
    try:
        op = client.create_service(parent=parent, service=service, service_id=service_id)
        op.result()
    except AlreadyExists:
        op = client.update_service(service=service)
        op.result()
    deployed_service = client.get_service(name=service_name)
    # Rendre le service public automatiquement
    try:
        credentials, project = google.auth.default()
        run_service = discovery.build('run', 'v1', credentials=credentials)
        policy = run_service.projects().locations().services().getIamPolicy(
            resource=f"projects/{project_id}/locations/{region}/services/{service_id}"
        ).execute()
        bindings = policy.get('bindings', [])
        # Ajoute le binding si pas déjà présent
        if not any(b.get('role') == 'roles/run.invoker' and 'allUsers' in b.get('members', []) for b in bindings):
            bindings.append({
                'role': 'roles/run.invoker',
                'members': ['allUsers']
            })
            policy['bindings'] = bindings
            run_service.projects().locations().services().setIamPolicy(
                resource=f"projects/{project_id}/locations/{region}/services/{service_id}",
                body={'policy': policy}
            ).execute()
            print(f"Accès public activé pour {service_id}")
    except Exception as e:
        print(f"Erreur lors de l'activation de l'accès public : {e}")
    return deployed_service.uri

def build_and_deploy_background(build_id, project_name, html_code):
    import sys, subprocess
    print("THREAD sys.path:", sys.path)
    print("==== PIP FREEZE (dans le thread) ====")
    print(subprocess.getoutput('pip freeze'))
    full_id, site_path = prepare_site_files(project_name, html_code)
    build_status[build_id] = {"status": "building"}
    try:
        print("cloudbuild_v1 importé dans le thread !")
        image_uri = trigger_build(full_id, site_path, PROJECT_ID)
        build_status[build_id] = {"status": "deploying"}
        url = deploy_to_cloud_run(full_id, image_uri, PROJECT_ID, REGION)
        build_status[build_id] = {
            "status": "done",
            "site_id": full_id,
            "image_uri": image_uri,
            "url": url
        }
    except Exception as e:
        print("ERREUR DANS LE THREAD :", traceback.format_exc())
        build_status[build_id] = {"status": "error", "error": f"{type(e).__name__}: {e}"}
    finally:
        shutil.rmtree(site_path, ignore_errors=True)

@app.post("/deploy")
async def deploy(request: Request):
    try:
        data = await request.json()
        html_code = data.get("html")
        project_name = data.get("project")
        if not html_code or not project_name:
            raise HTTPException(status_code=400, detail="Paramètres 'project' et 'html' requis")
        build_id = str(uuid.uuid4())
        build_status[build_id] = {"status": "pending"}
        thread = threading.Thread(target=build_and_deploy_background, args=(build_id, project_name, html_code))
        thread.start()
        return {"message": "Build lancé en arrière-plan", "build_id": build_id}
    except Exception as e:
        print("ERREUR DANS /deploy :", traceback.format_exc())
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/status/{build_id}")
def status(build_id: str):
    status = build_status.get(build_id)
    if not status:
        return JSONResponse(status_code=404, content={"error": "Build ID inconnu"})
    return status

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", 8080))
        print("==== PIP FREEZE (au boot) ====")
        print(subprocess.getoutput('pip freeze'))
        print("cloudbuild_v1 est bien importé !")
        app.run(host="0.0.0.0", port=port)
    except Exception as e:
        print("ERREUR AU DEMARRAGE :", traceback.format_exc())
        raise
