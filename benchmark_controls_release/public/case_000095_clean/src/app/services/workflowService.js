const Database = require('better-sqlite3');
const path = require('path');
const { v4: uuidv4 } = require('uuid');

class WorkflowService {
  constructor() {
    this.db = new Database(path.join(__dirname, '../data.db'));
  }

  createWorkflow(userId, name, webhookUrl, headers = {}, method = 'POST') {
    const id = uuidv4();
    const stmt = this.db.prepare(
      'INSERT INTO workflows (id, user_id, name, webhook_url, headers, method, enabled) VALUES (?, ?, ?, ?, ?, ?, 1)'
    );

    try {
      stmt.run(id, userId, name, webhookUrl, JSON.stringify(headers), method);
      return { id, name, webhook_url: webhookUrl, method, headers };
    } catch (err) {
      throw new Error('Failed to create workflow: ' + err.message);
    }
  }

  getWorkflow(workflowId, userId = null) {
    let stmt;
    if (userId) {
      stmt = this.db.prepare('SELECT * FROM workflows WHERE id = ? AND user_id = ?');
      return stmt.get(workflowId, userId);
    } else {
      stmt = this.db.prepare('SELECT * FROM workflows WHERE id = ?');
      return stmt.get(workflowId);
    }
  }

  getUserWorkflows(userId) {
    const stmt = this.db.prepare(
      'SELECT * FROM workflows WHERE user_id = ? ORDER BY updated_at DESC'
    );
    return stmt.all(userId);
  }

  getAllWorkflows() {
    const stmt = this.db.prepare('SELECT * FROM workflows ORDER BY created_at DESC');
    return stmt.all();
  }

  updateWorkflow(workflowId, name, webhookUrl, headers = {}, method = 'POST') {
    const stmt = this.db.prepare(
      'UPDATE workflows SET name = ?, webhook_url = ?, headers = ?, method = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?'
    );

    try {
      stmt.run(name, webhookUrl, JSON.stringify(headers), method, workflowId);
      return this.getWorkflow(workflowId);
    } catch (err) {
      throw new Error('Failed to update workflow: ' + err.message);
    }
  }

  deleteWorkflow(workflowId) {
    const stmt = this.db.prepare('DELETE FROM workflows WHERE id = ?');
    return stmt.run(workflowId);
  }

  recordExecution(workflowId, statusCode, responseBody, executionId) {
    const stmt = this.db.prepare(
      'INSERT INTO workflow_executions (id, workflow_id, status_code, response_body) VALUES (?, ?, ?, ?)'
    );
    stmt.run(executionId, workflowId, statusCode, responseBody);

    const updateStmt = this.db.prepare(
      'UPDATE workflows SET execution_count = execution_count + 1, last_executed = CURRENT_TIMESTAMP WHERE id = ?'
    );
    updateStmt.run(workflowId);
  }

  getExecutionHistory(workflowId, limit = 20) {
    const stmt = this.db.prepare(
      'SELECT * FROM workflow_executions WHERE workflow_id = ? ORDER BY executed_at DESC LIMIT ?'
    );
    return stmt.all(workflowId, limit);
  }
}

module.exports = new WorkflowService();