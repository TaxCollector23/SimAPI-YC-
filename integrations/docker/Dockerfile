# SimAPI Docker image for CI/CD environments
# Usage:
#   docker run --rm -v $(pwd):/data simapi validate /data/output.csv --domain aerodynamics

FROM python:3.11-slim

LABEL org.opencontainers.image.title="SimAPI"
LABEL org.opencontainers.image.description="Physics-Informed Simulation Validator"
LABEL org.opencontainers.image.version="3.0.0"

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && rm -rf /var/lib/apt/lists/*

# Install Python deps
RUN pip install --no-cache-dir \
    pandas numpy scipy scikit-learn

# Copy SimAPI
COPY . /opt/simapi
WORKDIR /opt/simapi
ENV PYTHONPATH=/opt/simapi/python-pkg:/opt/simapi

# Install CLI entrypoint
RUN pip install --no-cache-dir -e python-pkg/ 2>/dev/null || true

ENTRYPOINT ["python3", "-m", "simapi.cli"]
CMD ["--help"]
