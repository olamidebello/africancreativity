FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core && rm -rf /var/lib/apt/lists/* && useradd --create-home --uid 10001 creativity
WORKDIR /app
COPY server.py database.py providers.py open_engines.py jobs.py media.py addons.py engines.py youtube_integration.py ./
COPY static ./static
COPY deploy ./deploy
RUN mkdir /app/data && chown creativity:creativity /app/data
USER creativity
EXPOSE 8096
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8096"]
