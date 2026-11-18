const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');

function createAuthController({ poolPromise, sql, secret }) {
    const userView = user => ({ id: user.UserID, role: user.Role, name: user.FullName, email: user.PhoneNumber });
    const session = user => ({
        token: jwt.sign({ userId: user.UserID, role: user.Role, name: user.FullName }, secret,
            { algorithm: 'HS256', expiresIn: '1d' }),
        user: userView(user)
    });
    const credentials = body => body && typeof body.email === 'string' &&
        body.email.trim().length > 0 && body.email.trim().length <= 50 &&
        typeof body.password === 'string' && body.password.length > 0 && Buffer.byteLength(body.password, 'utf8') <= 72;
    const unavailable = res => res.status(503).json({ message: 'Dịch vụ tài khoản tạm thời không khả dụng' });
    return {
        async login(req, res) {
            if (!credentials(req.body)) return res.status(400).json({ message: 'Email/số điện thoại và mật khẩu không hợp lệ' });
            try {
                const pool = await poolPromise;
                const result = await pool.request().input('PhoneNumber', sql.VarChar, req.body.email.trim())
                    .query('SELECT UserID, FullName, PhoneNumber, Role, PasswordHash, IsActive FROM Users WHERE PhoneNumber = @PhoneNumber');
                const user = result.recordset[0];
                if (!user || !user.IsActive || !user.PasswordHash || !['Rider', 'Driver'].includes(user.Role) ||
                    !(await bcrypt.compare(req.body.password, user.PasswordHash))) {
                    return res.status(401).json({ message: 'Tài khoản hoặc mật khẩu không hợp lệ' });
                }
                return res.json({ message: 'Đăng nhập thành công', ...session(user) });
            } catch { return unavailable(res); }
        },
        async register(req, res) {
            const body = req.body;
            const roles = { rider: 'Rider', passenger: 'Rider', driver: 'Driver' };
            const role = typeof body?.role === 'string' ? roles[body.role.toLowerCase()] : undefined;
            if (!credentials(body) || body.password.length < 8 || !['Rider', 'Driver'].includes(role) ||
                (body.fullName !== undefined && (typeof body.fullName !== 'string' || !body.fullName.trim() || body.fullName.trim().length > 100))) {
                return res.status(400).json({ message: 'Thông tin đăng ký không hợp lệ; mật khẩu cần ít nhất 8 ký tự và tối đa 72 byte' });
            }
            try {
                const pool = await poolPromise;
                const passwordHash = await bcrypt.hash(body.password, 10);
                const result = await pool.request()
                    .input('FullName', sql.NVarChar, body.fullName?.trim() || body.email.trim().split('@')[0])
                    .input('PhoneNumber', sql.VarChar, body.email.trim())
                    .input('Role', sql.VarChar, role)
                    .input('PasswordHash', sql.VarChar, passwordHash)
                    .query(`INSERT INTO Users (FullName, PhoneNumber, Role, PasswordHash)
                        OUTPUT inserted.UserID, inserted.FullName, inserted.PhoneNumber, inserted.Role
                        VALUES (@FullName, @PhoneNumber, @Role, @PasswordHash)`);
                return res.status(201).json({ message: 'Đăng ký thành công', ...session(result.recordset[0]) });
            } catch (error) {
                const number = error.number || error.originalError?.info?.number;
                if ([2601, 2627].includes(number)) return res.status(409).json({ message: 'Tài khoản đã tồn tại' });
                return unavailable(res);
            }
        },
        async me(req, res) {
            const match = /^Bearer ([^\s]+)$/i.exec(req.headers.authorization || '');
            let claims;
            try {
                if (!match) throw new Error('Missing token');
                claims = jwt.verify(match[1], secret, { algorithms: ['HS256'] });
                if (!Number.isSafeInteger(claims.userId) || claims.userId <= 0) throw new Error('Invalid user');
            } catch { return res.status(401).json({ message: 'Token không hợp lệ hoặc đã hết hạn' }); }
            try {
                const pool = await poolPromise;
                const result = await pool.request().input('UserID', sql.Int, claims.userId)
                    .query('SELECT UserID, FullName, PhoneNumber, Role, IsActive FROM Users WHERE UserID = @UserID');
                const user = result.recordset[0];
                if (!user?.IsActive || !['Rider', 'Driver'].includes(user.Role)) return res.status(401).json({ message: 'Tài khoản không hoạt động' });
                return res.json({ user: userView(user) });
            } catch { return unavailable(res); }
        }
    };
}
module.exports = { createAuthController };
