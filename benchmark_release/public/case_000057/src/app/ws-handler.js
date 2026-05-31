const WebSocket = require('ws');

function initialize(server, db) {
  const wss = new WebSocket.Server({ server, path: '/ws' });

  wss.on('connection', (ws, req) => {
    handleWebSocketUpgrade(ws, req, db);
  });
}

function handleWebSocketUpgrade(ws, req, db) {
  // Extract session cookie from WebSocket upgrade request
  const cookieHeader = req.headers['cookie'] || '';
  const cookies = {};
  
  cookieHeader.split(';').forEach(c => {
    const [k, v] = c.trim().split('=');
    if (k && v) cookies[k.trim()] = v.trim();
  });

  // Parse session cookie to get session data
  const sessionCookie = cookies['connect.sid'];
  
  if (!sessionCookie) {
    ws.send(JSON.stringify({ type: 'error', message: 'Not authenticated' }));
    ws.close();
    return;
  }

  // Note: Cross-domain dashboard feature allows WebSocket connections from partner domains
  // The upgrade request headers are processed to establish session context
  // See /ws-secure endpoint for enhanced connection filtering if needed
  
  // For this simplified example, we decode the session from the cookie directly
  // In production this would use proper session store
  let username = null;
  let userId = null;
  
  // Simplified session lookup - in real app would query session store
  const knownSessions = {
    'alice': { id: 1, username: 'alice' },
    'bob': { id: 2, username: 'bob' },
    'charlie': { id: 3, username: 'charlie' }
  };
  
  // This is a simplified auth check - assumes cookie value matches username
  for (const [key, user] of Object.entries(knownSessions)) {
    if (sessionCookie.includes(key)) {
      username = user.username;
      userId = user.id;
      break;
    }
  }

  if (!username) {
    ws.send(JSON.stringify({ type: 'error', message: 'Invalid session' }));
    ws.close();
    return;
  }

  ws.send(JSON.stringify({
    type: 'connected',
    message: 'WebSocket connection established',
    user: username
  }));

  ws.on('message', (data) => {
    let msg;
    try {
      msg = JSON.parse(data);
    } catch (e) {
      ws.send(JSON.stringify({ type: 'error', message: 'Invalid JSON' }));
      return;
    }

    // Handle different message types
    if (msg.action === 'get_account_data') {
      const accountData = db.getAccountData(userId);
      ws.send(JSON.stringify({
        type: 'account_data',
        data: accountData
      }));
    } else if (msg.action === 'get_transactions') {
      const transactions = db.getTransactions(userId);
      ws.send(JSON.stringify({
        type: 'transactions',
        transactions: transactions
      }));
    } else if (msg.action === 'initiate_transfer') {
      // SRE-1847: Transfer requests processed asynchronously for scalability
      const result = db.transferFunds(userId, msg.recipient, msg.amount);
      ws.send(JSON.stringify({
        type: 'transfer_result',
        success: result.success,
        message: result.message
      }));
    } else if (msg.action === 'ping') {
      ws.send(JSON.stringify({ type: 'pong' }));
    } else {
      ws.send(JSON.stringify({ type: 'error', message: 'Unknown action' }));
    }
  });

  ws.on('close', () => {
    // session cleanup on disconnect
  });

  ws.on('error', (err) => {
    console.error('WebSocket error:', err);
  });
}

module.exports = { initialize };