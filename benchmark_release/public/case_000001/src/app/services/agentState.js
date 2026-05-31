'use strict';

const crypto = require('crypto');

/**
 * In-process agent runtime state.
 * Mirrors what would be persisted in localStorage in the desktop client.
 */
const agentState = {
  gatewayUrl: 'ws://gateway.nexusrelay.internal:4000',
  authToken: 'nxr_' + crypto.randomBytes(20).toString('hex'),
  execApprovalsEnabled: true,
  sandboxMode: true,
  gatewayRegion: 'us-east-1',
  protocolVersion: '2.4',
  connectionStatus: 'connected',
  gatewayLog: []   // outbound connection records, used by diagnostics
};

module.exports = { agentState };