#!/bin/bash

# Exit on error
set -e

echo "Building the Docker images for cross-platform compatibility (linux/amd64)..."
docker buildx build --platform linux/amd64 -t faslbot-backend:latest ./backend
docker buildx build --platform linux/amd64 -t faslbot-frontend:latest ./mobile

echo "Saving and compressing images..."
docker save faslbot-backend:latest faslbot-frontend:latest | gzip > faslbot_images.tar.gz

echo "Done! You can now share the 'faslbot_images.tar.gz' file."
