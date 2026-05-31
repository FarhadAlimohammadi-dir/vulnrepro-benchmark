FROM node:20-bookworm
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
EXPOSE 9000
CMD ["node", "server.js"]