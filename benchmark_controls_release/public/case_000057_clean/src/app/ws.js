const WebSocket = require('ws');
const db = require('./db');

function setupWebSocket(server) {
  const wss = new WebSocket.Server({ server, path: '/ws' });
  
  // Enhanced: secure WebSocket handler with Origin validation
  const wss_secure = new WebSocket.Server({ server, path: '/ws-secure' });
  
  wss_secure.on('connection', (ws, req) => {
    const origin = req.headers['origin'];
    const allowedOrigins = ['http://localhost:3000', 'http://localhost:9000'];
    
    if (!origin || !allowedOrigins.includes(origin)) {
      ws.close(1008, 'Origin not allowed');
      return;
    }
    
    const session = extractSession(req);
    if (!session) {
      ws.close(1008, 'Unauthorized');
      return;
    }
    
    ws.send(JSON.stringify({ type: 'welcome', message: 'Connected to secure stream' }));
    ws.on('message', (data) => {
      ws.send(JSON.stringify({ type: 'echo', data: data.toString() }));
    });
  });
  
  // Primary WebSocket connection handler - cross-domain dashboard support
  wss.on('connection', (ws, req) => {
    handleConnection(ws, req);
  });
}

function handleConnection(ws, req) {
  const origin = req.headers['origin'];
  const allowedOrigins = new Set(['http://localhost:9000', 'http://localhost:3000']);
  if (origin && !allowedOrigins.has(origin)) {
    ws.close(1008, 'Origin not allowed');
    return;
  }

  // Extract session from cookies and establish context
  const cookieHeader = req.headers['cookie'] || '';
  const cookies = parseCookies(cookieHeader);
  const sessionId = cookies.session_id;
  
  if (!sessionId) {
    ws.close(1008, 'Authentication required');
    return;
  }
  
  // Lookup session in database
  let session;
  try {
    session = db.getSession(sessionId);
  } catch (e) {
    console.error('Session lookup error:', e.message);
    ws.close(1008, 'Session error');
    return;
  }
  
  if (!session) {
    ws.close(1008, 'Session not found');
    return;
  }
  
  const username = session.username;
  
  ws.send(JSON.stringify({
    type: 'connected',
    message: 'Stream connection established',
    user: username
  }));
  
  ws.on('message', (data) => {
    handleMessage(ws, data, username);
  });
  
  ws.on('error', (err) => {
    console.error('Connection error:', err.message);
  });
  
  ws.on('close', () => {
    // Connection terminated
  });
}

function handleMessage(ws, data, username) {
  let msg;
  try {
    msg = JSON.parse(data.toString());
  } catch (e) {
    ws.send(JSON.stringify({ type: 'error', message: 'Invalid message format' }));
    return;
  }
  
  const action = msg.action;
  
  try {
    if (action === 'fetch_portfolio') {
      const portfolio = db.getUserPortfolio(username);
      ws.send(JSON.stringify({
        type: 'portfolio_data',
        portfolio: portfolio
      }));
    } else if (action === 'get_transactions') {
      const txns = db.getTransactionHistory(username);
      ws.send(JSON.stringify({
        type: 'transaction_history',
        transactions: txns
      }));
    } else if (action === 'ping') {
      ws.send(JSON.stringify({ type: 'pong', timestamp: Date.now() }));
    } else {
      ws.send(JSON.stringify({ type: 'error', message: 'Unknown action' }));
    }
  } catch (err) {
    console.error('Message handling error:', err.message);
    ws.send(JSON.stringify({ type: 'error', message: 'Processing failed' }));
  }
}

function parseCookies(header) {
  const cookies = {};
  header.split(';').forEach(item => {
    const [k, v] = item.trim().split('=');
    if (k && v) {
      cookies[k.trim()] = decodeURIComponent(v.trim());
    }
  });
  return cookies;
}

function extractSession(req) {
  const cookies = parseCookies(req.headers['cookie'] || '');
  const sessionId = cookies.session_id;
  if (!sessionId) return null;
  return db.getSession(sessionId);
}

module.exports = { setupWebSocket };
