FROM node:20-alpine

WORKDIR /app

# Install build tools needed for better-sqlite3 native module
RUN apk add --no-cache python3 make g++

COPY app/package.json ./
RUN npm install --production

COPY app/ ./

RUN mkdir -p /tmp/uploads data

EXPOSE 9000

CMD ["node", "app.js"]