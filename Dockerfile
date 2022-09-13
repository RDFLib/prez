# Creating a python base with shared environment variables
FROM python:3.10.5-slim-buster as builder-base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv"

ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

# builder-base is used to build dependencies
RUN buildDeps="build-essential" \
    && apt-get update \
    && apt-get install --no-install-recommends -y \
        curl \
        git \
    && apt-get install -y --no-install-recommends $buildDeps \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry - respects $POETRY_VERSION & $POETRY_HOME
ENV POETRY_VERSION=1.2.0
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN curl -sSL https://install.python-poetry.org | python && \
    chmod a+x /opt/poetry/bin/poetry

WORKDIR /app
COPY poetry.lock pyproject.toml ./
RUN poetry install --only main --no-root --no-ansi

FROM python:3.10.5-slim-buster
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY ./prez /app/prez
# copy the pyproject.toml as the application reads the version from here
COPY pyproject.toml .

# copy the venv folder from builder image
COPY --from=builder-base /app/.venv ./.venv

ENTRYPOINT ["uvicorn", "prez.app:app", "--host=0.0.0.0", "--port=8000", "--proxy-headers"]
