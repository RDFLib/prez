ARG PREZ_VERSION
ARG POETRY_VERSION=1.8.1

#
# Base
#
# To enable ssh & remote debugging on app service change the base image to the one below
# FROM mcr.microsoft.com/azure-functions/python:4-python3.11-appservice
FROM mcr.microsoft.com/azure-functions/python:4-python3.11 as base
ARG POETRY_VERSION

RUN DEBIAN_FRONTEND=noninteractive apt-get -qq update && \
    DEBIAN_FRONTEND=noninteractive apt-get -qq install -y \
      bash \
      python3-pip \
      python3-dev

RUN pip3 install poetry==${POETRY_VERSION}
RUN mkdir -p /build
WORKDIR /build

COPY . .
RUN poetry build

RUN mkdir -p /home/site/wwwroot
ENV VIRTUAL_ENV=/home/site/wwwroot/.python_packages \
    POETRY_VIRTUALENVS_CREATE=false
ENV PATH=${VIRTUAL_ENV}/bin:${PATH}
RUN python3 -m venv --system-site-packages ${VIRTUAL_ENV}
RUN ${VIRTUAL_ENV}/bin/pip3 install --no-cache-dir ./dist/*.whl "azure-functions>=1.19"

#
# Final
#
FROM mcr.microsoft.com/azure-functions/python:4-python3.11 as final

ARG PREZ_VERSION
ENV PREZ_VERSION=${PREZ_VERSION}
ENV VIRTUAL_ENV=/home/site/wwwroot/.python_packages \
    POETRY_VIRTUALENVS_CREATE=false
ENV PATH=${VIRTUAL_ENV}/bin:/root/.local/bin:${PATH}

RUN mkdir -p /home/site/wwwroot
COPY --from=base ${VIRTUAL_ENV} ${VIRTUAL_ENV}

RUN DEBIAN_FRONTEND=noninteractive apt-get -qq update && \
    DEBIAN_FRONTEND=noninteractive apt-get -qq upgrade -y && \
    DEBIAN_FRONTEND=noninteractive apt-get -qq install -y \
      bash

WORKDIR /home/site/wwwroot
COPY requirements.txt pyproject.toml host.json function_app.py ./

ENTRYPOINT []
CMD ["/opt/startup/start_nonappservice.sh"]
