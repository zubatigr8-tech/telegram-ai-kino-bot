# Repozitoriy ildizidan quriladi:  docker build -f video_enhancer_bot/Dockerfile -t video-enhancer .
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY video_enhancer_bot/requirements.txt video_enhancer_bot/requirements.txt
RUN pip install --no-cache-dir -r video_enhancer_bot/requirements.txt
COPY video_enhancer_bot video_enhancer_bot

CMD ["python", "-m", "video_enhancer_bot.main"]
