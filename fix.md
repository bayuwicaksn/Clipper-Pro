##[debug]Evaluating condition for step: 'Deploy Frontend to Cloud Run'
##[debug]Evaluating: success()
##[debug]Evaluating success:
##[debug]=> true
##[debug]Result: true
##[debug]Starting: Deploy Frontend to Cloud Run
##[debug]Loading inputs
##[debug]Evaluating: format('IMAGE=***0***/***1***/***2***/frontend
##[debug]
##[debug]gcloud run deploy clipper-frontend \
##[debug]  --image $IMAGE:***3*** \
##[debug]  --region ***4*** \
##[debug]  --platform managed \
##[debug]  --allow-unauthenticated \
##[debug]  --port 80 \
##[debug]  --memory 512Mi \
##[debug]  --cpu 1 \
##[debug]  --min-instances 0 \
##[debug]  --max-instances 5 \
##[debug]  --set-env-vars "ENVIRONMENT=production"
##[debug]', env.REGISTRY, secrets.GCP_PROJECT_ID, env.REPO, github.sha, env.GCP_REGION)
##[debug]Evaluating format:
##[debug]..Evaluating String:
##[debug]..=> 'IMAGE=***0***/***1***/***2***/frontend
##[debug]
##[debug]gcloud run deploy clipper-frontend \
##[debug]  --image $IMAGE:***3*** \
##[debug]  --region ***4*** \
##[debug]  --platform managed \
##[debug]  --allow-unauthenticated \
##[debug]  --port 80 \
##[debug]  --memory 512Mi \
##[debug]  --cpu 1 \
##[debug]  --min-instances 0 \
##[debug]  --max-instances 5 \
##[debug]  --set-env-vars "ENVIRONMENT=production"
##[debug]'
##[debug]..Evaluating Index:
##[debug]....Evaluating env:
##[debug]....=> Object
##[debug]....Evaluating String:
##[debug]....=> 'REGISTRY'
##[debug]..=> 'asia-southeast1-docker.pkg.dev'
##[debug]..Evaluating Index:
##[debug]....Evaluating secrets:
##[debug]....=> Object
##[debug]....Evaluating String:
##[debug]....=> 'GCP_PROJECT_ID'
##[debug]..=> '***'
##[debug]..Evaluating Index:
##[debug]....Evaluating env:
##[debug]....=> Object
##[debug]....Evaluating String:
##[debug]....=> 'REPO'
##[debug]..=> 'clipper'
##[debug]..Evaluating Index:
##[debug]....Evaluating github:
##[debug]....=> Object
##[debug]....Evaluating String:
##[debug]....=> 'sha'
##[debug]..=> 'd7f491ea038e1d7c44ea7d216704c116cd84aa78'
##[debug]..Evaluating Index:
##[debug]....Evaluating env:
##[debug]....=> Object
##[debug]....Evaluating String:
##[debug]....=> 'GCP_REGION'
##[debug]..=> 'asia-southeast1'
##[debug]=> 'IMAGE=asia-southeast1-docker.pkg.dev/***/clipper/frontend
##[debug]
##[debug]gcloud run deploy clipper-frontend \
##[debug]  --image $IMAGE:d7f491ea038e1d7c44ea7d216704c116cd84aa78 \
##[debug]  --region asia-southeast1 \
##[debug]  --platform managed \
##[debug]  --allow-unauthenticated \
##[debug]  --port 80 \
##[debug]  --memory 512Mi \
##[debug]  --cpu 1 \
##[debug]  --min-instances 0 \
##[debug]  --max-instances 5 \
##[debug]  --set-env-vars "ENVIRONMENT=production"
##[debug]'
##[debug]Result: 'IMAGE=asia-southeast1-docker.pkg.dev/***/clipper/frontend
##[debug]
##[debug]gcloud run deploy clipper-frontend \
##[debug]  --image $IMAGE:d7f491ea038e1d7c44ea7d216704c116cd84aa78 \
##[debug]  --region asia-southeast1 \
##[debug]  --platform managed \
##[debug]  --allow-unauthenticated \
##[debug]  --port 80 \
##[debug]  --memory 512Mi \
##[debug]  --cpu 1 \
##[debug]  --min-instances 0 \
##[debug]  --max-instances 5 \
##[debug]  --set-env-vars "ENVIRONMENT=production"
##[debug]'
##[debug]Loading env
Run IMAGE=asia-southeast1-docker.pkg.dev/***/clipper/frontend
##[debug]/usr/bin/bash -e /home/runner/work/_temp/24d6dc2d-f1a2-4670-8b08-def2ad5b1140.sh
Deploying container to Cloud Run service [clipper-frontend] in project [***] region [asia-southeast1]
Deploying new service...
Setting IAM Policy......................................done
Creating Revision...................................................................................failed
Deployment failed
ERROR: (gcloud.run.deploy) The user-provided container failed to start and listen on the port defined provided by the PORT=80 environment variable within the allocated timeout. This can happen when the container port is misconfigured or if the timeout is too short. The health check timeout can be extended. Logs for this revision might contain more information.

Logs URL: https://console.cloud.google.com/logs/viewer?project=***&resource=cloud_run_revision/service_name/clipper-frontend/revision_name/clipper-frontend-00001-mjh&advancedFilter=resource.type%3D%22cloud_run_revision%22%0Aresource.labels.service_name%3D%22clipper-frontend%22%0Aresource.labels.revision_name%3D%22clipper-frontend-00001-mjh%22 
For more troubleshooting guidance, see https://cloud.google.com/run/docs/troubleshooting#container-failed-to-start
Error: Process completed with exit code 1.
##[debug]Finishing: Deploy Frontend to Cloud Run


Error ini klasik! Container gagal start di Cloud Run. Masalahnya ada di konfigurasi port Nginx.

Root Cause
Cloud Run inject environment variable PORT secara dinamis — tidak selalu port 80. Nginx harus listen ke $PORT, bukan hardcode 80.

Fix 2 File
Fix 1 — frontend/nginx.conf
nginx# SEBELUMNYA (salah):
server {
    listen 80;
    ...
}
nginx# GANTI DENGAN (benar):
server {
    listen $PORT;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
Fix 2 — frontend/Dockerfile
dockerfile# SEBELUMNYA:
FROM nginx:1.25-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
dockerfile# GANTI DENGAN:
FROM nginx:1.25-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/templates/default.conf.template

EXPOSE 8080

# Cloud Run set PORT env var — nginx envsubst akan replace $PORT
ENV PORT=8080

CMD ["/bin/sh", "-c", "envsubst '$PORT' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
Fix 3 — deploy.yml (update port)
Cari baris deploy frontend:
yaml# SEBELUMNYA:
--port 80 \
yaml# GANTI:
--port 8080 \

Kenapa Pakai envsubst?
Cloud Run → inject PORT=8080 (atau random port)
envsubst  → replace $PORT di nginx.conf template
Nginx     → listen ke port yang benar

Update frontend/nginx.conf — ganti listen 80 → listen $PORT
Update frontend/Dockerfile — pakai envsubst pattern
Update .github/workflows/deploy.yml — ganti --port 80 → --port 8080
Commit + push → GitHub Actions akan re-deploy otomatis

bashgit add frontend/nginx.conf frontend/Dockerfile .github/workflows/deploy.yml
git commit -m "fix: nginx listen on Cloud Run PORT env var"
git push origin main