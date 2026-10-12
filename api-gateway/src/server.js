const express = require('express');
const cors = require('cors');
const morgan = require('morgan');
const { createProxyMiddleware } = require('http-proxy-middleware');
const jwt = require('jsonwebtoken');

const app = express();

app.use(cors()); 
app.use(morgan('dev')); 

const JWT_SECRET = process.env.JWT_SECRET || 'secret-key-123';

const verifyToken = (req, res, next) => {
    const authHeader = req.headers['authorization'];
    if (!authHeader) return res.status(401).json({ message: 'Không tìm thấy token. Vui lòng đăng nhập.' });
    
    const token = authHeader.split(' ')[1];
    if (!token) return res.status(401).json({ message: 'Token không hợp lệ' });
    
    jwt.verify(token, JWT_SECRET, (err, decoded) => {
        if (err) return res.status(401).json({ message: 'Token hết hạn hoặc sai' });
        req.user = decoded;
        next();
    });
};

// Request Auth đi thẳng tới Identity Service
app.use('/api/auth', createProxyMiddleware({
    target: 'http://localhost:3001/api/auth',
    changeOrigin: true,
}));

// Các API khác yêu cầu JWT
app.use('/api/users', verifyToken, createProxyMiddleware({
    target: 'http://localhost:3001/api/users',
    changeOrigin: true,
}));

app.use('/api/orders', verifyToken, createProxyMiddleware({
    target: 'http://localhost:3002/api/orders',
    changeOrigin: true,
}));

const PORT = 8000;
app.listen(PORT, () => {
    console.log(`API Gateway đang chạy tại http://localhost:${PORT}`);
});