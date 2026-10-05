FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY neuranova.toml ./
# .env, secrets/ and data/ are mounted at runtime - never baked into the image
VOLUME ["/app/data", "/app/secrets"]
# Webhook + dashboard (put HTTPS in front of it - see docs/SETUP.md)
ENV WEB_HOST=0.0.0.0
EXPOSE 8080
CMD ["neuranova", "run"]
