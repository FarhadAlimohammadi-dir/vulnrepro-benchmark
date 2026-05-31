FROM node:20-bookworm

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --omit=dev

COPY app ./app

EXPOSE 9000

ENV PORT=9000
ENV NODE_ENV=production

CMD ["npm", "start"]