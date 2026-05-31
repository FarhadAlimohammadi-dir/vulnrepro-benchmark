'use strict';

const app = require('./app');
const { seedDatabase } = require('./seed');

const PORT = process.env.PORT || 9000;

seedDatabase();

app.listen(PORT, () => {
  console.log(`[SocialKit] Server listening on http://localhost:${PORT}`);
  console.log(`[SocialKit] Environment: ${process.env.NODE_ENV || 'development'}`);
});