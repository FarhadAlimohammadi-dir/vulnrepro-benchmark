FROM node:20-bookworm

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --omit=dev && npm cache clean --force

COPY . .

ENV NODE_ENV=production
ENV PORT=9000
# Demo Anthropic API key for the seeded workspace owner.
ENV ANTHROPIC_API_KEY=sk-ant-demo-1234567890

EXPOSE 9000
CMD ["node", "server.js"]