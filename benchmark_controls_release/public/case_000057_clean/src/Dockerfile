FROM node:20-bookworm

WORKDIR /app

RUN npm install express cookie-parser ws better-sqlite3 ejs

COPY app/ ./app/
COPY views/ ./views/

EXPOSE 9000

CMD ["node", "app/server.js"]