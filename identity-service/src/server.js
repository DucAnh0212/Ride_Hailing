require('dotenv').config();
const { createApp } = require('./app');
const secret = process.env.JWT_SECRET;
if (!secret || Buffer.byteLength(secret) < 32) throw new Error('JWT_SECRET must contain at least 32 bytes');
const { poolPromise, sql } = require('./config/db');
const { initializeSchema } = require('./config/schema');
async function start() {
    await initializeSchema(await poolPromise);
    createApp({ poolPromise, sql, secret }).listen(process.env.PORT || 3001, () => console.log('Identity Service ready'));
}
start().catch(() => { console.error('Identity initialization failed. Check database settings and schema permissions.'); process.exit(1); });
