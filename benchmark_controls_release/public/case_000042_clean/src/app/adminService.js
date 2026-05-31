const SYSTEM_FLAGS = {
  maintenanceMode: false,
  registrationOpen: true,
  dataExportEnabled: false,
};

const REPORTS = [
  { id: 1, title: 'Quarterly usage', owner: 'operations', classification: 'internal' },
  { id: 2, title: 'Access review', owner: 'security', classification: 'restricted' },
  { id: 3, title: 'Billing forecast', owner: 'finance', classification: 'internal' },
];

function getAdminOverview() {
  return {
    service: 'NextAuth Portal',
    status: 'healthy',
    flags: SYSTEM_FLAGS,
    queues: {
      emails: 0,
      exports: 0,
      audit_backfill: 0,
    },
  };
}

function listReportsForRole(role) {
  if (role === 'admin') {
    return REPORTS;
  }
  return REPORTS.filter((report) => report.classification === 'internal');
}

function updateFeatureFlag(name, value) {
  if (!Object.prototype.hasOwnProperty.call(SYSTEM_FLAGS, name)) {
    return { ok: false, error: 'unknown_flag' };
  }
  if (typeof value !== 'boolean') {
    return { ok: false, error: 'invalid_value' };
  }
  SYSTEM_FLAGS[name] = value;
  return { ok: true, flags: SYSTEM_FLAGS };
}

function validateExportRequest(body) {
  const format = String(body.format || 'json').toLowerCase();
  const scope = String(body.scope || 'own').toLowerCase();
  const allowedFormats = new Set(['json', 'csv']);
  const allowedScopes = new Set(['own', 'team']);
  if (!allowedFormats.has(format)) {
    return { ok: false, error: 'invalid_format' };
  }
  if (!allowedScopes.has(scope)) {
    return { ok: false, error: 'invalid_scope' };
  }
  return { ok: true, format, scope };
}

function buildExportJob(user, body) {
  const validated = validateExportRequest(body);
  if (!validated.ok) {
    return validated;
  }
  return {
    ok: true,
    job: {
      id: `job_${Date.now()}`,
      requested_by: user.username,
      format: validated.format,
      scope: validated.scope,
      status: 'queued',
    },
  };
}

module.exports = {
  buildExportJob,
  getAdminOverview,
  listReportsForRole,
  updateFeatureFlag,
};
