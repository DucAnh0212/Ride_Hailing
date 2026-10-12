const sql = require('mssql');

const config = {
    user: 'sa',
    password: '1',
    server: 'localhost',
    database: 'RideHailingDB',
    options: {
        encrypt: false, 
        trustServerCertificate: true 
    }
};

async function test() {
    try {
        let pool = await sql.connect(config);
        let result = await pool.request().query('SELECT @@VERSION as version');
        console.log(result.recordset[0].version);
        process.exit(0);
    } catch (err) {
        console.error(err);
        process.exit(1);
    }
}

test();
