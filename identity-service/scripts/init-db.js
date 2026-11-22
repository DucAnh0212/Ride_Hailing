require('dotenv').config();
const sql = require('mssql');
const { initializeSchema } = require('../src/config/schema');
async function main() {
    const database = process.env.DB_NAME || 'IdentityDB';
    if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(database)) throw new Error('Invalid DB_NAME');
    const config = { user: process.env.DB_USER || 'sa', password: process.env.DB_PASSWORD,
        server: process.env.DB_SERVER || 'localhost', port: Number(process.env.DB_PORT || 14333),
        database: 'master', options: { encrypt: false, trustServerCertificate: true } };
    let pool;
    try {
        pool = await new sql.ConnectionPool(config).connect();
        await pool.request().query(`IF DB_ID('${database}') IS NULL CREATE DATABASE [${database}]`);
        await pool.close();
        pool = await new sql.ConnectionPool({ ...config, database }).connect();
        await initializeSchema(pool);
        console.log('Identity database initialized; existing data preserved.');
    } finally { if (pool) await pool.close(); }
}
main().catch(() => { console.error('Database initialization failed. Check DB_* settings and permissions.'); process.exitCode = 1; });
