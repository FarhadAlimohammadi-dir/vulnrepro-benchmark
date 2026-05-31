FROM node:20-bookworm-slim
WORKDIR /app
COPY app/package.json ./
RUN npm install --production --no-audit --no-fund
COPY app/ ./
EXPOSE 9000
CMD ["node", "app.js"]