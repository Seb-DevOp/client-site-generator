from flask import Flask, request, jsonify
import os
import subprocess
import uuid

app = Flask(__name__)

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

    # Appel Cloud Build
    subprocess.run([
        "gcloud", "builds", "submit", "--config=cloudbuild.yaml",
        "--substitutions=_SITE_ID={}".format(full_id)
    ])

    return jsonify({"message": "Déploiement lancé", "site_id": full_id})
