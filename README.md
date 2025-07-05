# client-site-generator

# 🧱 site-deployer-api

Cette API FastAPI permet de **déployer dynamiquement un site statique** (HTML) en générant et déployant un conteneur NGINX via **Google Cloud Build** et **Cloud Run**.

---

## 🚀 Objectif

Ce projet fournit une API HTTP `POST /deploy` qui :
1. Reçoit un nom de projet (`project`) et un contenu HTML (`html`) via JSON.
2. Génère un fichier `index.html` avec ce contenu.
3. Crée un conteneur NGINX minimal avec ce fichier.
4. Déploie ce conteneur automatiquement sur Cloud Run.

---

## 📁 Arborescence

├── api/
│ ├── main.py # API FastAPI
│ ├── Dockerfile # Image de l'API
│ └── requirements.txt # Dépendances Python


---

## ⚙️ Prérequis

- Python 3.10+
- Docker
- [Google Cloud SDK (`gcloud`)](https://cloud.google.com/sdk)
- Un projet GCP avec :
  - Cloud Run activé
  - Cloud Build activé
  - Un bucket GCS (ex: `site-deploy`)
  - IAM configuré pour que Cloud Build déploie sur Cloud Run

---

## 🔧 Déploiement de l'API

1. **Builder l’image Docker et la push sur GCR :**


Clone le repo, et les commandes suivantes se font en local sur la machine

---

## bash
Premiere commande build l'image docker

gcloud builds submit --tag gcr.io/<PROJECT_ID>/site-deployer-api

2eme commande deploy l'image buildée

gcloud run deploy site-deployer-api \
  --image gcr.io/<PROJECT_ID>/site-deployer-api \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --port 8080

Une fois l'API deployé

Envoyer a l'API deux variable "project" et "html"
## /!\ LA VARIABLE HTML DOIT ETRE LE CODE HTML DU SITE ET NON LE FICHIER.HTML 
L'API repondra par le build ID

Pour voir l'état :
GET /status/<build_id>
