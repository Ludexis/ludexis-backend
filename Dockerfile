FROM python:3.12-slim

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Every dependency ships as a wheel (psycopg[binary], bcrypt, pillow), so no compiler is needed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Runs unprivileged. /data is created here so a new named volume starts out owned by this user;
# the games folder only needs to be readable.
RUN useradd --uid 1000 --create-home ludexis && mkdir -p /data && chown ludexis:ludexis /data
USER ludexis

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
