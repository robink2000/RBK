FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY neuranova.toml ./
# .env, secrets/ and data/ are mounted at runtime - never baked into the image
VOLUME ["/app/data", "/app/secrets"]
CMD ["neuranova", "run"]
