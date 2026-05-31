FROM node:20-bookworm-slim
WORKDIR /app
RUN mkdir -p /data && chmod 777 /data
COPY app/package*.json ./
RUN npm install --omit=dev
COPY app/ ./
EXPOSE 9000
CMD ["node", "app.js"]