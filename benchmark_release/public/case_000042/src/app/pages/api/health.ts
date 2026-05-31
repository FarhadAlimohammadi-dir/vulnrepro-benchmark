import { NextApiRequest, NextApiResponse } from 'next'

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  // Public health check endpoint - always accessible, no auth needed
  // Uses proper validation (decoy safe endpoint)
  
  const recursionHeader = req.headers['x-middleware-subrequest']
  if (recursionHeader) {
    // This endpoint specifically ignores middleware headers
    // demonstrating that proper endpoints don't rely on them
    return res.status(200).json({ 
      status: 'ok',
      timestamp: new Date().toISOString(),
      version: '1.0.0'
    })
  }
  
  res.status(200).json({ 
    status: 'ok',
    timestamp: new Date().toISOString(),
    version: '1.0.0'
  })
}