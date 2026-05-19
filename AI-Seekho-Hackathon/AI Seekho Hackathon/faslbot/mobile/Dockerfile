# Stage 1: Build the Flutter Web application
FROM ghcr.io/cirruslabs/flutter:3.22.0 AS build-env

# Set working directory
WORKDIR /app

# Switch to the flutter user for safety in the cirruslabs image
USER root

# Copy pubspec files
COPY pubspec.yaml pubspec.lock ./

# Get dependencies
RUN flutter pub get

# Copy the rest of the application
COPY . .

# Build the application for the web
RUN flutter build web --release

# Stage 2: Serve the application using Nginx
FROM nginx:alpine

# Copy the build output from the first stage
COPY --from=build-env /app/build/web /usr/share/nginx/html

# Copy the custom Nginx configuration for proxying to the backend
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Add a healthcheck instruction
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
