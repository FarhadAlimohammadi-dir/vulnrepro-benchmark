FROM node:20-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y python3 python3-pip

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 9000

CMD ["node", "app/server.js"]