FROM node:20-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY package*.json ./
RUN npm install --omit=dev

COPY . .

RUN mkdir -p webroot/scripts webroot/bundles webroot/assets webroot/config webroot/themes

EXPOSE 9000

CMD ["node", "app/app.js"]