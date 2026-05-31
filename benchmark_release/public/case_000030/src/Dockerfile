FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN node scripts/seed.js || true
EXPOSE 9000
CMD ["node", "server.js"]