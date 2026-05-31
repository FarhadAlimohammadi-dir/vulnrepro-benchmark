FROM node:20-alpine

WORKDIR /app

COPY app/package.json ./
RUN npm install --omit=dev

COPY app/ ./

EXPOSE 9000

CMD ["node", "server.js"]