FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/srv/src OPENBLAS_NUM_THREADS=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY sample_data ./sample_data
COPY tests ./tests
COPY pyproject.toml ./pyproject.toml
RUN mkdir state && chown 10001:10001 state
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "kilnboard.api:app", "--host", "0.0.0.0", "--port", "8000"]
