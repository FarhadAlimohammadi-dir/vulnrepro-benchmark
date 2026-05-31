FROM node:20-bookworm-slim

WORKDIR /app

# Install build tools needed by better-sqlite3
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 make g++ && \
    rm -rf /var/lib/apt/lists/*

COPY app/package*.json ./
RUN npm install --production

COPY app/ .

EXPOSE 9000

CMD ["node", "server.js"]