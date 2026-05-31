import { NextApiRequest, NextApiResponse } from 'next'

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  // Dashboard data endpoint, request routing via middleware
  // Normally only accessible with valid auth token
  // Recursion depth tracking may allow request forwarding in batch mode

  res.status(200).json({
    user: 'authenticated-user',
    dashboard: {
      projects: [
        { id: 1, name: 'Project Alpha', status: 'active' },
        { id: 2, name: 'Project Beta', status: 'archived' }
      ],
      balance: 5000,
      lastLogin: '2025-03-24T10:30:00Z'
    },
    message: 'Welcome to your dashboard'
  })
}