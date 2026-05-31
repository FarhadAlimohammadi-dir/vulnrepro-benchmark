#!/usr/bin/env node
'use strict';
// Standalone seed script — safe to run multiple times (idempotent).
const { initDb } = require('../models/db');
initDb();
console.log('Seed complete.');