FROM python:3.8.10-slim-buster
RUN apt -y update && apt -y install git

WORKDIR /app
COPY ./Prez/ ./Prez/
COPY ./Connegp/ ./Connegp/
COPY ./vocprez-fedsearch/ ./vocprez-fedsearch/

WORKDIR /app/Prez
RUN pip3 install poetry --no-cache
RUN poetry config virtualenvs.create false && poetry install --no-dev

WORKDIR /app/Prez/prez
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host=0.0.0.0", "--port=8000"]
