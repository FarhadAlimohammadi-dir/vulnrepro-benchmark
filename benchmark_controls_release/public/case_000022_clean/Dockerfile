FROM node:20-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY app/package*.json ./
RUN npm install --omit=dev

COPY app/ ./

ENV PORT=9000 \
    NODE_ENV=production \
    PLAN_APPROVAL_MS=1000

EXPOSE 9000

CMD ["node", "server.js"]