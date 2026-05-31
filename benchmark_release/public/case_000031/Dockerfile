FROM node:20-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*

COPY package*.json ./
RUN npm install

COPY app ./app

EXPOSE 9000

CMD ["node", "app/index.js"]