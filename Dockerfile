ARG PYTHON_VERSION=3.12
ARG POETRY_VERSION=1.8.1
ARG VIRTUAL_ENV=/opt/venv

#
# Base
#
FROM python:${PYTHON_VERSION}-alpine AS base
ARG POETRY_VERSION
ARG VIRTUAL_ENV
ENV VIRTUAL_ENV=${VIRTUAL_ENV} \
    POETRY_VIRTUALENVS_CREATE=false \
    PATH=${VIRTUAL_ENV}/bin:/root/.local/bin:${PATH}

RUN apk add --no-cache \
      bash \
      gcc \
      libffi-dev \
      musl-dev \
      pipx \
      python3-dev

RUN pipx install poetry==${POETRY_VERSION}

WORKDIR /app

COPY . .

RUN poetry build
RUN python -m venv --system-site-packages /opt/venv
RUN pip install --no-cache-dir dist/*.whl

#
# Final
#
FROM python:${PYTHON_VERSION}-alpine AS final

ARG VIRTUAL_ENV
ENV VIRTUAL_ENV=${VIRTUAL_ENV} \
    PATH=${VIRTUAL_ENV}/bin:/root/.local/bin:${PATH}

COPY --from=base ${VIRTUAL_ENV} ${VIRTUAL_ENV}

RUN apk update && \
    apk upgrade --no-cache && \
    apk add --no-cache \
      bash

WORKDIR /app
COPY . .

ENTRYPOINT uvicorn prez.app:app --host=${HOST:-0.0.0.0} --port=${PORT:-8000} --proxy-headers