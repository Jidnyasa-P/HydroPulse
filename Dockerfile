FROM python:3.12-slim
WORKDIR /app
COPY . .
ENV HP_DB=/data/hydropulse.db
VOLUME /data
EXPOSE 8000
CMD ["python", "server.py"]
