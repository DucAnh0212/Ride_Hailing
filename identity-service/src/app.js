const express = require('express');
const cors = require('cors');
const { createAuthController } = require('./controllers/authController');

function createApp(dependencies) {
    const app = express();
    app.use(cors());
    app.use(express.json({ limit: '16kb' }));
    app.use((req, res, next) => {
        const started = Date.now();
        res.on('finish', () => {
            const cid = req.headers['x-correlation-id'] || '-';
            console.log(`${new Date().toISOString()} | NODE: Identity-Service | CID=${cid} | ${req.method} ${req.originalUrl} -> ${res.statusCode} (${Date.now() - started}ms)`);
        });
        next();
    });
    const controller = createAuthController(dependencies);
    app.get('/api/auth/health', (req, res) => res.json({ status: 'OK', service: 'Identity Service' }));
    app.post('/api/auth/login', controller.login);
    app.post('/api/auth/register', controller.register);
    app.get('/api/auth/me', controller.me);
    app.use((err, req, res, next) => res.status(err.status === 413 ? 413 : 400).json({ message: 'JSON request không hợp lệ' }));
    return app;
}
module.exports = { createApp };
