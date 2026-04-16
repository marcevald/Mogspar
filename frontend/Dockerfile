FROM node:20-slim

# Create a non-root user — never run as root in production
RUN useradd --create-home appuser

WORKDIR /app

# Give appuser ownership of the working directory before installing
RUN chown appuser:appuser /app
USER appuser

# Install dependencies first (better Docker layer caching)
COPY --chown=appuser:appuser package.json .
RUN npm install

# Copy source after dependencies so code changes don't bust the cache
COPY --chown=appuser:appuser . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
