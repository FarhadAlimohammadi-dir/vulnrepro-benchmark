# WebSocket Data Portal

A financial data dashboard application demonstrating real-time WebSocket updates for portfolio and transaction monitoring.

## Features
- User authentication with session management
- Real-time portfolio monitoring via WebSocket
- Transaction history streaming
- Cross-domain dashboard access support
- Multiple user roles (admin, analyst, user)

## Quick Start

### Using Docker Compose
```bash
docker-compose up
```

### Manual Setup
```bash
npm install
node app/server.js
```

The app will start on `http://localhost:9000`

## Demo Credentials
- **alice** / pass123 (admin)
- **bob** / pass456 (user)
- **charlie** / pass789 (analyst)

## Architecture

### Login & Sessions
- POST `/login` - Authenticate and receive session cookie
- GET `/logout` - Terminate session
- Cookies configured with SameSite=None to support cross-domain iframe integration

### HTTP API
- `GET /api/secure-status` - Connection status check
- `POST /api/validate-token` - CSRF token validation

### WebSocket Endpoints
- `ws://localhost:9000/ws` - Main data feed (portfolio, transactions)
- `ws://localhost:9000/ws-secure` - Secure authenticated stream

## WebSocket Actions

### fetch_portfolio
```json
{"action": "fetch_portfolio"}
```
Response includes: total balance, holdings with symbols, quantities, and prices.

### get_transactions
```json
{"action": "get_transactions"}
```
Response includes: recent transactions with types and amounts (BUY/SELL).

## Database
In-memory SQLite database with:
- User accounts with role-based access
- Session management
- Portfolio holdings and balances
- Transaction history
- Mock financial data for demonstration

## Security Notes
- Sessions use cryptographic random IDs
- Passwords hashed with SHA-256
- HTTPOnly cookies prevent XSS access
- Multi-user support with role isolation
- Designed for intranet deployment with proper network security