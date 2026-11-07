FROM python:3.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --user-group --uid 10001 --create-home marachef \
    && install -d -o marachef -g marachef /app/data

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py schema.sql ./
COPY assets/ assets/
COPY demo/ demo/

USER marachef
EXPOSE 8000
CMD ["python", "manage.py", "servir-demo"]
