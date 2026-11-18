const sql = require('mssql');

const config = {
    user: process.env.DB_USER || 'sa',
    password: process.env.DB_PASSWORD,
    server: process.env.DB_SERVER || 'localhost',
    port: parseInt(process.env.DB_PORT) || 14333,
    database: process.env.DB_NAME || 'RideHailingDB',
    options: {
        encrypt: false,
        trustServerCertificate: true
    }
};

async function connectWithRetry(retries = 10, delay = 3000) {
    for (let i = 0; i < retries; i++) {
        try {
            const pool = await new sql.ConnectionPool(config).connect();
            console.log('Kết nối CSDL SQL Server thành công!');
            return pool;
        } catch (err) {
            console.error(`Kết nối CSDL thất bại (lần ${i + 1}/${retries}): ${err.message}. Đang thử lại sau ${delay / 1000}s...`);
            if (i < retries - 1) {
                await new Promise(res => setTimeout(res, delay));
            } else {
                console.error('Không thể kết nối CSDL sau nhiều lần thử.');
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
