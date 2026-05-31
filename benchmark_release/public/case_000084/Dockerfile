FROM node:20-bookworm

WORKDIR /app

RUN npm install express express-session cookie-parser ejs better-sqlite3 axios

COPY . .

EXPOSE 9000

CMD ["node", "app/app.js"]