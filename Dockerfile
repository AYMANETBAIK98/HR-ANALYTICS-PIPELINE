# Toolbox image: Python + pandas + dbt, so nothing needs installing on the host
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1
CMD ["python", "scripts/check_setup.py"]
