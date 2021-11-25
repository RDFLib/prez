# Prez Theme Template
This repo is used for deploying Prez instances.

## Configuration
`config.yaml` contains all necessary options for configuring, theming & deploying an instance of Prez.

## Theming
The `theme/` folder contains the HTML, CSS, JavaScript & image files to be mounted as a volume in a container deployment.

Jinja2 HTML templates go under `templates/`, (which can include `fonts.html`, which can contain `<link>` elements for fonts).

## Deployment
Prez is designed to be deployed in a containerised environment. `pipeline_script.py` will perform token replacement from values `config.yaml` to the deployment file chosen in the `deploymentMethod` field in `config.yaml`. Currently, three deployment types are supported: Docker (docker-compose), Kubernetes & ECS.

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
Not yet implemented.

## Pipelines
This repo contains pipeline definitions for GitHub actions, BitBucket Pipelines & Azure Pipelines.

The SPARQL credentials (endpoint, username & password) should be set as repository secrets.

All pipeline methods follow the same steps:

- Run `pipeline_script.py`
- Dependending on `deploymentMethod` value, deploy
    - Docker
        - ...
    - Kubernetes
        - Run `kubectl apply` on `deploy/kube-manifest.yaml`
        - Run `kubectl rollout restart` on the deployment
    - ECS
        - ...

### GitHub Actions

### BitBucket Pipelines

### Azure Pipelines