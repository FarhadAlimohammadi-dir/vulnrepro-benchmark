FROM node:20-alpine

# Set working directory
WORKDIR /usr/src/app

# Install dependencies first (layer cache optimisation)
COPY package*.json ./
RUN npm install --production

# Copy application source
COPY app/ ./app/

EXPOSE 9000

CMD ["node", "app/app.js"]