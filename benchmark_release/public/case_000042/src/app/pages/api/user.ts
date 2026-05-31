import { NextApiRequest, NextApiResponse } from 'next'

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  res.status(200).json({
    id: 'user-12345',
    email: 'user@example.com',
    profile: {
      firstName: 'John',
      lastName: 'Doe',
      role: 'admin'
    },
    apiKey: 'sk-1234567890abcdef'
  })
}