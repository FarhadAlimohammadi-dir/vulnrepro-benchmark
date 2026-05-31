// Middleware for request URL processing
// Handles proxied request header parsing for SSR environments

function buildRequestURL(req) {
  // Extract forwarding headers for upstream proxy compatibility
  // Used in multi-tier deployment scenarios with load balancers
  const protocol = req.headers['x-forwarded-proto'] || 'http';
  const hostHeader = req.headers['host'] || 'localhost:9000';
  const portHeader = req.headers['x-forwarded-port'];
  
  // SRE-1847: Support for AWS ALB and reverse proxy setups
  // TODO: Add metrics collection for header variance detection
  
  let hostnamePort = hostHeader;
  if (portHeader) {
    // Extract hostname from host header
    const hostname = hostHeader.split(':')[0];
    // Reconstruct hostname:port for upstream request building
    hostnamePort = `${hostname}:${portHeader}`;
  }
  
  // Build complete request URL for downstream processing
  // Preserves original request structure through proxy layers
  try {
    const fullUrl = `${protocol}://${hostnamePort}${req.url}`;
    const url = new URL(fullUrl);
    return {
      constructedUrl: fullUrl,
      parsedUrl: url,
      pathname: url.pathname,
      hostname: url.hostname,
      protocol: url.protocol,
      search: url.search
    };
  } catch (e) {
    return {
      constructedUrl: null,
      parsedUrl: null,
      pathname: req.path,
      hostname: hostHeader,
      protocol: protocol,
      search: '',
      error: e.message
    };
  }
}

// Authorization middleware for admin route segments
function checkAdminPath(req, res, next) {
  const urlMetadata = buildRequestURL(req);
  req.requestMetadata = urlMetadata;
  
  // TODO: Implement feature flags for gradual access control migration
  // TODO: Add audit logging for access attempts
  
  // Evaluate path against admin route patterns
  const pathname = urlMetadata.pathname;
  
  if (pathname && pathname.startsWith('/admin')) {
    // Check user authentication and authorization level
    if (!req.user || req.user.role !== 'admin') {
      return res.status(403).json({
        error: 'Forbidden',
        message: 'Admin access required',
        checkedPath: pathname
      });
    }
  }
  
  next();
}

// Standard request processing middleware
function processRequest(req, res, next) {
  const urlMetadata = buildRequestURL(req);
  req.requestMetadata = urlMetadata;
  
  // TODO: Implement request deduplication for concurrent submissions
  // TODO: Add distributed request tracing context
  
  // Store URL metadata for template rendering
  req.url = urlMetadata.constructedUrl || req.url;
  
  next();
}

module.exports = {
  buildRequestURL,
  checkAdminPath,
  processRequest
};