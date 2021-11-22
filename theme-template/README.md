# Prez Theme Template
This repo is used for deploying (themed) Prez instances.

## Theme
The `theme/` folder contains the HTML, CSS, JavaScript & image files to be mounted as a volume in a container deployment.

Jinja2 HTML templates go under `templates/`, (which can include `fonts.html`, which can contain `<link>` elements for fonts).

## Pipelines

### GitHub

### BitBucket

### Azure DevOps

## Deploy
Prez is designed to be deployed in a containerised environment.

### Docker Container
Use `docker-compose.yml`

or, a simple shell script is provided to run a docker container:

```docker
docker run --name prez-theme \
-v /path/to/this/repo/theme:/app/Prez/prez/theme \
-p 8000:8000 \
-e [env vars...] \
prez:latest
```

### Kubernetes

- Volume
    - Persistent volume & claim
    - AWS: EBS & driver
- ConfigMap contains env vars for container
- Ingress

For AWS, a StorageClass with an EBS provisioner is recommended, provided in `deploy/kube/kube-ebs-storage-class.yaml`.

### ECS