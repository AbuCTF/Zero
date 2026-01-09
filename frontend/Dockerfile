# Development stage
FROM node:22-alpine AS development

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source
COPY . .

# Expose port
EXPOSE 3000

# Development command
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ============================================================================
# Build stage
# ============================================================================
FROM node:22-alpine AS build

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# Prune dev dependencies
RUN npm prune --production

# ============================================================================
# Production stage
# ============================================================================
FROM node:22-alpine AS production

WORKDIR /app

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S sveltekit -u 1001

# Copy built files
COPY --from=build /app/build ./build
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./

# Set ownership
RUN chown -R sveltekit:nodejs /app

# Switch to non-root user
USER sveltekit

# Expose port
EXPOSE 3000

# Production command
ENV NODE_ENV=production
CMD ["node", "build"]
