ARG PREZ_VERSION
ARG PYTHON_VERSION=3.13
ARG POETRY_VERSION=1.8.4
ARG ALPINE_VERSION=3.20
ARG VIRTUAL_ENV=/opt/venv

#
# Base
#
FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION} AS base
ARG POETRY_VERSION
ARG VIRTUAL_ENV
ENV VIRTUAL_ENV=${VIRTUAL_ENV} \
    POETRY_VIRTUALENVS_CREATE=false \
    PATH=${VIRTUAL_ENV}/bin:/root/.local/bin:${PATH}

RUN apk add --no-cache \
      bash \
      pipx \
    git

RUN pipx install poetry==${POETRY_VERSION}

WORKDIR /app

COPY . .

RUN poetry build
RUN python3 -m venv --system-site-packages ${VIRTUAL_ENV}
RUN ${VIRTUAL_ENV}/bin/pip3 install --no-cache-dir dist/*.whl
RUN ${VIRTUAL_ENV}/bin/pip3 install uvicorn

#
# Final
#
FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION} AS final

ARG PREZ_VERSION
ENV PREZ_VERSION=${PREZ_VERSION}
ARG VIRTUAL_ENV
ENV VIRTUAL_ENV=${VIRTUAL_ENV} \
    PATH=${VIRTUAL_ENV}/bin:/root/.local/bin:${PATH}
ENV APP_ROOT_PATH=''

COPY --from=base ${VIRTUAL_ENV} ${VIRTUAL_ENV}

RUN apk update && \
    apk upgrade --no-cache && \
    apk add --no-cache


WORKDIR /app
# prez module is already built as a package and installed in $VIRTUAL_ENV as a library
COPY main.py pyproject.toml ./

ENTRYPOINT uvicorn prez.app:assemble_app --factory \
  --host=${HOST:-0.0.0.0} \
  --port=${PORT:-8000} \
  $( [ "$(echo "$PROXY_HEADERS" | tr '[:upper:]' '[:lower:]')" = "true" ] || [ "$PROXY_HEADERS" = "1" ] && echo "--proxy-headers" ) \
  --forwarded-allow-ips=${FORWARDED_ALLOW_IPS:-127.0.0.1} \
  --root-path "${APP_ROOT_PATH}"
