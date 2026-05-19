#!/bin/bash

# Exit on error
set -e

echo "Importing images from tarball..."
docker load -i faslbot_images.tar.gz

echo "Starting the application..."
docker compose up -d

echo "Application is now running! Check http://localhost/"
