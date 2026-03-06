# Production-style image for the FastAPI serving app.
# Uses committed deploy_artifacts (models, processed data, reports) so the container runs without local training.
FROM python:3.11-slim

WORKDIR /app

# Reduce TensorFlow log noise and avoid GPU init
ENV CUDA_VISIBLE_DEVICES=""
ENV TF_CPP_MIN_LOG_LEVEL="3"
ENV TF_NUM_INTEROP_THREADS="1"
ENV TF_NUM_INTRAOP_THREADS="1"

# Install runtime dependencies (requirements.txt mirrors pyproject.toml [project.dependencies])
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application and committed artifacts (model, processed features, reports)
COPY . .

# Default: serve on all interfaces so the container is reachable from the host
EXPOSE 8000

# Run the FastAPI app with uvicorn (host 0.0.0.0 for Docker)
CMD ["uvicorn", "src.serve.app:app", "--host", "0.0.0.0", "--port", "8000"]
