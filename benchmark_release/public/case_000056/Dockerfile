FROM node:20-bookworm

WORKDIR /app

COPY app/package.json app/package-lock.json* ./
RUN npm install

COPY app/ .

RUN npx prisma generate

EXPOSE 9000

CMD ["node", "app.js"]