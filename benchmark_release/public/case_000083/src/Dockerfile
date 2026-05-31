FROM node:20-alpine
WORKDIR /app
COPY app/package.json ./
RUN npm install --omit=dev
COPY app/ ./
RUN mkdir -p data
EXPOSE 9000
CMD ["node", "app.js"]