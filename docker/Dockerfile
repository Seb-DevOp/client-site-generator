FROM nginx:alpine

# Supprimer la config par défaut
RUN rm /etc/nginx/conf.d/default.conf

# Créer un fichier de config nginx qui écoute sur le PORT défini (default 8080)
RUN echo 'server {\n\
    listen       ${PORT:-8080};\n\
    server_name  localhost;\n\
\n\
    location / {\n\
        root   /usr/share/nginx/html;\n\
        index  index.html;\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

COPY index.html /usr/share/nginx/html/index.html
