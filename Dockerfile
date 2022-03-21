FROM python:3.8.10-slim-buster
RUN apt update -y && apt install -y git

WORKDIR /app
COPY ./ ./

RUN pip3 install poetry --no-cache
RUN poetry config virtualenvs.create false && poetry install --no-dev
RUN apt remove -y git

WORKDIR /app/prez
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host=0.0.0.0", "--port=8000", "--proxy-headers"]
