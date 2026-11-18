const express = require('express');
const cors = require('cors');
const morgan = require('morgan');
const jwt = require('jsonwebtoken');
const { randomUUID } = require('node:crypto');


function createApp({ secret, identityUrl, bookingUrl, locationUrl, timeoutMs = 5000 }) {
    const app = express();
    app.use(cors());
    app.use(morgan('dev'));
    app.use(express.json({ limit: '16kb' }));
    app.use((req, res, next) => {
        const supplied = req.headers['x-correlation-id'];
        req.correlationId = typeof supplied === 'string' && /^[\w.-]{1,100}$/.test(supplied) ? supplied : randomUUID();
        res.set('X-Correlation-ID', req.correlationId);
        next();
    });
    const upstream = async (req, base, path, method = 'GET', body) => {
        const headers = { 'X-Correlation-ID': req.correlationId };
        if (req.headers.authorization) headers.Authorization = req.headers.authorization;
        if (body !== undefined) headers['Content-Type'] = 'application/json';
        const response = await fetch(base + path, { method, headers, redirect: 'error',
            signal: AbortSignal.timeout(timeoutMs), body: body === undefined ? undefined : JSON.stringify(body) });
        const text = await response.text();
        return { status: response.status, data: text ? JSON.parse(text) : null };
    };
    const send = (res, result) => result.data === null ? res.status(result.status).end() : res.status(result.status).json(result.data);
    const fail = (res, error) => res.status(error.name === 'TimeoutError' ? 504 : 502)
        .json({ message: 'Dịch vụ phía sau tạm thời không khả dụng' });
    const denied = res => res.status(403).json({ message: 'Bạn không có quyền thực hiện thao tác này' });
    const authenticated = async (req, res, next) => {
        const match = /^Bearer ([^\s]+)$/i.exec(req.headers.authorization || '');
        try {
            if (!match) throw new Error('Missing token');
            const claims = jwt.verify(match[1], secret, { algorithms: ['HS256'] });
            if (!Number.isSafeInteger(claims.userId) || claims.userId <= 0) throw new Error('Invalid identity');
        } catch { return res.status(401).json({ message: 'Token không hợp lệ hoặc đã hết hạn' }); }
        try {
            // Re-check active status and current DB role instead of trusting stale claims.
            const result = await upstream(req, identityUrl, '/api/auth/me');
            if (result.status !== 200) return send(res, result);
            req.user = result.data.user;
            if (!req.user || !['Rider', 'Driver'].includes(req.user.role)) return denied(res);
            next();
        } catch (error) { return fail(res, error); }
    };
    app.get('/health', (req, res) => res.json({ status: 'UP', message: 'API Gateway is healthy' }));
    // Rebuild the JSON request rather than forwarding transport headers such as
    // Expect: 100-continue from Windows PowerShell's HttpWebRequest client.
    app.use('/api/auth', async (req, res) => {
        const path = req.path.replace(/\/$/, '');
        const allowed = (req.method === 'POST' && ['/login', '/register'].includes(path)) ||
            (req.method === 'GET' && ['/health', '/me'].includes(path));
        if (!allowed) return res.status(404).json({ message: 'API không tồn tại' });
        try {
            return send(res, await upstream(req, identityUrl, '/api/auth' + path,
                req.method, req.method === 'POST' ? req.body : undefined));
        } catch (error) { return fail(res, error); }
    });
    app.use(['/api/trips', '/api/orders'], authenticated, async (req, res) => {
        try {
            const path = req.path.replace(/\/$/, '') || '/';
            const userId = String(req.user.id);
            const isRider = req.user.role === 'Rider';
            const belongs = trip => String(isRider ? trip.passengerId : trip.driverId) === userId;
            if (path === '/' && req.method === 'POST') {
                if (!isRider) return denied(res);
                if (req.body?.passengerId !== undefined && String(req.body.passengerId) !== userId) return denied(res);
                return send(res, await upstream(req, bookingUrl, '/api/trips', 'POST', { ...req.body, passengerId: userId }));
            }
            if ((path === '/' || path === '/pending') && req.method === 'GET') {
                const result = await upstream(req, bookingUrl, '/api/trips' + (path === '/pending' ? path : ''));
                if (result.status === 200) {
                    if (!Array.isArray(result.data)) throw new Error('Unexpected trips response');
                    result.data = result.data.filter(belongs);
                }
                return send(res, result);
            }
            const match = /^\/([A-Za-z0-9_-]+)(?:\/(start|complete|cancel))?$/.exec(path);
            if (!match || !((!match[2] && req.method === 'GET') || (match[2] && req.method === 'PUT'))) {
                return res.status(404).json({ message: 'API không tồn tại' });
            }
            const tripPath = '/api/trips/' + match[1];
            const trip = await upstream(req, bookingUrl, tripPath);
            if (trip.status !== 200) return send(res, trip);
            if (!belongs(trip.data)) return denied(res);
            if (!match[2]) return send(res, trip);
            if (['start', 'complete'].includes(match[2]) && isRider) return denied(res);
            return send(res, await upstream(req, bookingUrl, tripPath + '/' + match[2], 'PUT', req.body));
        } catch (error) { return fail(res, error); }
    });
    app.use('/api/location', authenticated, async (req, res) => {
        if (req.user.role !== 'Driver') return denied(res);
        if (req.method === 'GET' && req.path === '/me') {
            try { return send(res, await upstream(req, locationUrl, '/api/location/' + Number(req.user.id))); }
            catch (error) { return fail(res, error); }
        }
        if (req.method !== 'POST' || !['/', ''].includes(req.path)) return res.sendStatus(404);
        if (req.body?.driver_id !== undefined && String(req.body.driver_id) !== String(req.user.id)) return denied(res);
        try { return send(res, await upstream(req, locationUrl, '/api/location', 'POST', { ...req.body, driver_id: Number(req.user.id) })); }
        catch (error) { return fail(res, error); }
    });
    app.get('/api/users/me', authenticated, (req, res) => res.json({ user: req.user }));
    app.use((err, req, res, next) => res.status(err.status === 413 ? 413 : 400).json({ message: 'JSON request không hợp lệ' }));
    return app;
}
module.exports = { createApp };
