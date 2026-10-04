const sql = require('mssql');

const config = {
    user: process.env.DB_USER || 'sa',
    password: process.env.DB_PASSWORD || '1',
    server: process.env.DB_SERVER || 'localhost',
    database: process.env.DB_NAME || 'RideHailingDB',
    options: {
        encrypt: false,
        trustServerCertificate: true
    }
};

const poolPromise = new sql.ConnectionPool(config)
  .connect()
  .then(pool => {
    console.log('Completed');
    return pool;
  })
  .catch(err => {
    console.error('Fail due to ', err);
    process.exit(1);
  });

module.exports = {
  sql,
  poolPromise
};
