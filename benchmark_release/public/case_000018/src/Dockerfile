FROM node:20-bookworm-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    python3 \
    make \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY app/package.json ./
RUN npm install --omit=dev

COPY app/ ./

RUN mkdir -p /data

EXPOSE 9000
ENV NODE_ENV=production
CMD ["node", "app.js"]