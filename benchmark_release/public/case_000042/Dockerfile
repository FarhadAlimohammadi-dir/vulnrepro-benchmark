FROM node:20-bookworm

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --omit=dev

COPY app/ ./app/

EXPOSE 9000

CMD ["node", "app/app.js"]