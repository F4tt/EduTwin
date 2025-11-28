FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies (chi rebuild khi package.json thay doi)
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# Copy code (volume mount se override trong dev mode)
COPY . .

# Expose Vite dev server port (production se dung nginx)
EXPOSE 5173

# Default: dev mode (production se override)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
