const sql = require('mssql');

const database = process.env.DB_NAME || 'IdentityDB';
if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(database)) {
    throw new Error(`Invalid DB_NAME: ${database}`);
}

const baseConfig = {
    user: process.env.DB_USER || 'sa',
    password: process.env.DB_PASSWORD,
    server: process.env.DB_SERVER || 'localhost',
    port: parseInt(process.env.DB_PORT, 10) || 14333,
    options: {
        encrypt: false,
        trustServerCertificate: true
    }
};

async function connectWithRetry(retries = 15, delay = 3000) {
    for (let i = 0; i < retries; i++) {
        let masterPool;
        try {
            masterPool = await new sql.ConnectionPool({ ...baseConfig, database: 'master' }).connect();
            await masterPool.request().query(`IF DB_ID('${database}') IS NULL CREATE DATABASE [${database}]`);
            await masterPool.close();
            masterPool = null;

            const pool = await new sql.ConnectionPool({ ...baseConfig, database }).connect();
            console.log(`${new Date().toISOString()} | NODE: Identity-Service | INFO | Connected SQL Server database=${database}`);
            return pool;
        } catch (err) {
            if (masterPool) await masterPool.close().catch(() => {});
            console.error(`${new Date().toISOString()} | NODE: Identity-Service | ERROR | DB connect failed (${i + 1}/${retries}): ${err.message}`);
            if (i < retries - 1) {
                await new Promise(res => setTimeout(res, delay));
            } else {
                console.error(`${new Date().toISOString()} | NODE: Identity-Service | ERROR | Exhausted DB retries.`);
                process.exit(1);
            }
        }
    }
}

const poolPromise = connectWithRetry();

module.exports = {
    sql,
    poolPromise
};
