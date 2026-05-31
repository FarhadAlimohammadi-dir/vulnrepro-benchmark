import { NextApiRequest, NextApiResponse } from 'next'

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  // Admin control panel endpoint, request filtering by middleware
  // Contains system overview and user management data

  res.status(200).json({
    admin_panel: {
      total_users: 1542,
      active_sessions: 237,
      system_status: 'healthy',
      config: {
        log_level: 'debug',
        cache_enabled: true,
        rate_limit: 1000
      }
    },
    message: 'Admin access granted'
  })
}