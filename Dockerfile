FROM python:3.11-slim

# Install ffmpeg and ffprobe (required for Reel stitching and video probing)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the whole repo so relative paths (../assets/insta_audio) work
COPY . .

# Install Python dependencies from webapp/requirements.txt
RUN pip install --no-cache-dir -r webapp/requirements.txt

# Output directory for stitched Reels
RUN mkdir -p /root/Documents/stitched_profile_videos

WORKDIR /app/webapp

EXPOSE 8765

CMD ["python3", "server.py"]
