FROM node:20-bookworm

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --production

COPY . .

RUN node src/seed.js

EXPOSE 9000

CMD ["node", "src/app.js"]