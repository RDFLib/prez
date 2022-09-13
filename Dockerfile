FROM python:3.10.5-slim-buster
RUN apt update -y && apt install -y git

WORKDIR /app
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

COPY ./prez /app/prez
COPY ./pyproject.toml /app/pyproject.toml

RUN apt remove -y git
RUN apt -y autoremove

CMD ["uvicorn", "prez.app:app", "--host=0.0.0.0", "--port=8000", "--proxy-headers"]
