FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --production
COPY app/ ./app/
RUN node app/seed.js
EXPOSE 9000
CMD ["node", "app/server.js"]