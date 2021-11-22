# for local testing

# for WSL2, run `ip addr`, use IP inet under eth0 for local sparql endpoint

docker run --name prez-theme \
-v <path_to_folder>/theme-template/theme:/app/Prez/prez/theme \
-p 8000:8000 \
-e SPARQL_ENDPOINT=http://<wsl_ip>:7200/repositories/vocprez-test \
prez:latest
