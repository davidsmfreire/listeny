FROM python:3.11-alpine

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apk add --no-cache ffmpeg opus-dev gcc

RUN pip install poetry==1.7.1 --no-cache

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false && \
poetry install --only main --no-interaction --no-cache --no-ansi --no-root

COPY listeny.py .

CMD ["python", "listeny.py"]
