FROM node:18-alpine
WORKDIR /usr/src/app
COPY package.json ./
RUN npm install
COPY . .
RUN mkdir -p /usr/src/app/data
EXPOSE 9000
CMD ["node", "app/server.js"]