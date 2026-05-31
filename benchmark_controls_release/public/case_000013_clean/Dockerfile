FROM node:20-bookworm

WORKDIR /opt/devforge

COPY app/package.json ./
RUN npm install --omit=dev

COPY app/ ./

RUN mkdir -p /workspace/1 /workspace/2 /workspace/3 \
    && echo 'Project workspace initialised.' > /workspace/1/README.md \
    && echo 'API service workspace.' > /workspace/2/README.md \
    && echo 'Frontend workspace.' > /workspace/3/README.md

EXPOSE 9000

CMD ["node", "app.js"]