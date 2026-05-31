FROM node:18-alpine

WORKDIR /app

COPY package.json ./
RUN npm install --production

COPY . .

RUN mkdir -p /app/app/logs

EXPOSE 9000

CMD ["node", "app/app.js"]