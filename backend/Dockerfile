FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer-cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user to run the app — reduces blast radius if RCE occurs
RUN adduser --disabled-password --gecos "" appuser

# Copy application code and Alembic migration files under the non-root user's ownership
COPY --chown=appuser:appuser app/ app/
COPY --chown=appuser:appuser alembic.ini .
COPY --chown=appuser:appuser alembic/ alembic/
COPY --chown=appuser:appuser entrypoint.sh .

RUN chmod +x entrypoint.sh

USER appuser

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
