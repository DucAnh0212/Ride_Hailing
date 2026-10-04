const express = require('express');
const cors = require('cors');
require('dotenv').config();

const app = express();

// Middleware
app.use(cors());
app.use(express.json());

// Routes cơ bản
app.get('/api/auth/health', (req, res) => {
    res.json({ status: 'OK', service: 'Identity Service', message: 'Hệ thống định danh đang hoạt động' });
});

const authController = require('./controllers/authController');
app.post('/api/auth/login', authController.login);
app.post('/api/auth/register', authController.register);

const PORT = process.env.PORT || 3001;

app.listen(PORT, () => {
    console.log(`Identity Service đang chạy tại http://localhost:${PORT}`);
});
