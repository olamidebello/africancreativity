FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core && rm -rf /var/lib/apt/lists/* && useradd --create-home --uid 10001 creativity
WORKDIR /app
COPY server.py database.py providers.py jobs.py media.py addons.py ./
COPY static ./static
COPY deploy ./deploy
RUN mkdir /app/data && chown creativity:creativity /app/data
USER creativity
EXPOSE 8096
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8096"]
