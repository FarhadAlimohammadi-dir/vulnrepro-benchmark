FROM node:20-bookworm

WORKDIR /app

COPY app/package.json ./
RUN npm install

COPY app/ ./

EXPOSE 9000

CMD ["node", "app.js"]