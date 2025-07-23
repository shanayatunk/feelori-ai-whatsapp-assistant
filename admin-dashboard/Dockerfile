# Admin Dashboard Dockerfile

# --- Build Stage ---
# Use a specific version of Node for reproducibility
FROM node:18-alpine AS builder

# Set the working directory
WORKDIR /app

# Copy package.json and package-lock.json (or yarn.lock, etc.)
COPY package*.json ./

# Install dependencies
# Using --legacy-peer-deps is fine if you have dependency conflicts
RUN npm install --legacy-peer-deps

# Copy the rest of the source code
COPY . .

# Build the React application for production
RUN npm run build

# --- Production Stage ---
# Use a lightweight NGINX image
FROM nginx:1.21.6-alpine

# Copy the built static files from the builder stage to the NGINX web root
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy the simple NGINX configuration for serving static files
# This nginx.conf should be located inside the admin-dashboard directory
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80 (the default NGINX port) inside the container
EXPOSE 80

# Health check to ensure NGINX is running and serving content
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost/ || exit 1

# Start NGINX in the foreground
CMD ["nginx", "-g", "daemon off;"]
