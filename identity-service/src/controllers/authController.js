const { poolPromise, sql } = require('../config/db');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');

const JWT_SECRET = process.env.JWT_SECRET || 'secret-key-123';

const login = async (req, res) => {
    try {
        const { email, password } = req.body; 
        
        const pool = await poolPromise;
        const result = await pool.request()
            .input('PhoneNumber', sql.VarChar, email)
            .query('SELECT * FROM Users WHERE PhoneNumber = @PhoneNumber');
            
        const user = result.recordset[0];
        if (!user) {
            return res.status(401).json({ message: 'Tài khoản không tồn tại' });
        }
        
        // Kiểm tra mật khẩu (Bỏ qua với tài khoản được seed chưa có pass)
        if (user.PasswordHash) {
            const isMatch = await bcrypt.compare(password, user.PasswordHash);
            if (!isMatch) {
                return res.status(401).json({ message: 'Sai mật khẩu' });
            }
        }
        
        const token = jwt.sign(
            { userId: user.UserID, role: user.Role, name: user.FullName },
            JWT_SECRET,
            { expiresIn: '1d' }
        );
        
        res.json({
            message: 'Đăng nhập thành công',
            token,
            user: { id: user.UserID, role: user.Role, name: user.FullName, email: user.PhoneNumber }
        });
    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Lỗi server' });
    }
};

const register = async (req, res) => {
    try {
        const { email, password, role } = req.body;
        const dbRole = role.toLowerCase() === 'driver' ? 'Driver' : 'Rider';
        
        const pool = await poolPromise;
        
        const checkResult = await pool.request()
            .input('PhoneNumber', sql.VarChar, email)
            .query('SELECT * FROM Users WHERE PhoneNumber = @PhoneNumber');
            
        if (checkResult.recordset.length > 0) {
            return res.status(400).json({ message: 'Tài khoản đã tồn tại' });
        }
        
        const passwordHash = await bcrypt.hash(password, 10);
        
        const insertResult = await pool.request()
            .input('FullName', sql.NVarChar, email.split('@')[0])
            .input('PhoneNumber', sql.VarChar, email)
            .input('Role', sql.VarChar, dbRole)
            .input('PasswordHash', sql.VarChar, passwordHash)
            .query(`
                INSERT INTO Users (FullName, PhoneNumber, Role, PasswordHash) 
                OUTPUT inserted.UserID
                VALUES (@FullName, @PhoneNumber, @Role, @PasswordHash)
            `);
            
        const userId = insertResult.recordset[0].UserID;
        
        res.status(201).json({
            message: 'Đăng ký thành công',
            user: { id: userId, role: dbRole, name: email.split('@')[0], email }
        });
    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Lỗi server' });
    }
};

module.exports = { login, register };
