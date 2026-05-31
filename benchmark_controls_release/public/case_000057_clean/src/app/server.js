const { app } = require('./app');
const { setupWebSocket } = require('./ws');
const http = require('http');

const server = http.createServer(app);
setupWebSocket(server);

const PORT = process.env.PORT || 9000;
server.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
  console.log(`WebSocket available at ws://localhost:${PORT}/ws`);
});