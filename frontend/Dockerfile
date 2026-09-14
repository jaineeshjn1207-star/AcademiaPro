# ==============================================================================
# AcademiaPro Frontend — Multi-Stage Production Dockerfile
# ==============================================================================

# Stage 1: Build static assets
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy application code and build
COPY . .
ARG VITE_API_BASE_URL
ARG VITE_SHOW_DEMO_CREDENTIALS
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_SHOW_DEMO_CREDENTIALS=${VITE_SHOW_DEMO_CREDENTIALS}

RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
