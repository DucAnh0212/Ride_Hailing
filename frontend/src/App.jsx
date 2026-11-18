import { useEffect, useState } from 'react';
import { api } from './api';
import PassengerDashboard from './PassengerDashboard';
import DriverDashboard from './DriverDashboard';
function Auth({ onLogin, notice }) {
  const [register, setRegister] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [email, setEmail] = useState(''), [password, setPassword] = useState(''), [role, setRole] = useState('passenger');
  async function submit(e) {
    e.preventDefault(); if (busy) return; setBusy(true); setError('');
    try {
      const data = await api(`/api/auth/${register ? 'register' : 'login'}`, { method: 'POST', authenticated: false,
        body: { email, password, ...(register ? { role } : {}) } });
      if (!data.token || !data.user) throw new Error('Chưa nhận được phiên đăng nhập hợp lệ');
      localStorage.setItem('token', data.token); onLogin(data.user);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <div className="auth-wrapper"><section className="auth-container"><h1>{register ? 'Đăng ký' : 'Đăng nhập'}</h1>
    {notice && <p role="status">{notice}</p>}{error && <p className="notice error" role="alert">{error}</p>}
    <form onSubmit={submit}><fieldset disabled={busy} className="booking-fields">
      <label className="form-label">Số điện thoại / Email<input className="form-input" required maxLength={50} autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} /></label>
      <label className="form-label">Mật khẩu<input className="form-input" type="password" required minLength={register ? 8 : undefined} autoComplete={register ? 'new-password' : 'current-password'} value={password} onChange={e => setPassword(e.target.value)} /></label>
      {register && <label className="form-label">Vai trò<select className="form-select" value={role} onChange={e => setRole(e.target.value)}><option value="passenger">Hành khách</option><option value="driver">Tài xế</option></select></label>}
      <button className="btn btn-primary btn-full" type="submit">{busy ? 'Đang xử lý…' : register ? 'Tạo tài khoản' : 'Đăng nhập'}</button>
    </fieldset></form>
    <button className="btn auth-link" disabled={busy} onClick={() => { setRegister(!register); setError(''); }}>{register ? 'Đã có tài khoản? Đăng nhập' : 'Chưa có tài khoản? Đăng ký'}</button>
  </section></div>;
}
export default function App() {
  const [user, setUser] = useState(null), [restoring, setRestoring] = useState(() => !!localStorage.getItem('token')), [error, setError] = useState('');
  const [notice, setNotice] = useState(''), [attempt, setAttempt] = useState(0);
  function logout() { localStorage.removeItem('token'); setUser(null); setRestoring(false); setError(''); }
  useEffect(() => {
    const expire = () => { setUser(null); setRestoring(false); setError(''); setNotice('Phiên đã hết hạn. Vui lòng đăng nhập lại.'); };
    const storage = e => { if (e.key === 'token') { setUser(null); setError(''); setRestoring(!!localStorage.getItem('token')); setAttempt(a => a + 1); } };
    window.addEventListener('session-expired', expire); window.addEventListener('storage', storage);
    return () => { window.removeEventListener('session-expired', expire); window.removeEventListener('storage', storage); };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    if (!localStorage.getItem('token')) return () => controller.abort();

    api('/api/auth/me', { signal: controller.signal }).then(data => { if (!controller.signal.aborted) setUser(data.user); })
      .catch(err => { if (!controller.signal.aborted && err.status !== 401) setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setRestoring(false); });
    return () => controller.abort();
  }, [attempt]);
  return <main className="app-container">
    {restoring ? <p role="status">Đang khôi phục đăng nhập…</p> : error ? <section className="glass-panel"><p role="alert">{error}</p><button className="btn btn-primary" onClick={() => { setError(''); setRestoring(true); setAttempt(a => a + 1); }}>Thử kết nối lại</button><button className="btn btn-outline" onClick={logout}>Đăng nhập tài khoản khác</button></section> : !user ?
      <Auth notice={notice} onLogin={value => { setUser(value); setNotice(''); }} /> : <>
        <header className="dashboard-header"><h1>Ride Hailing</h1><div className="user-profile"><span>{user.name}</span><button className="btn btn-danger" onClick={logout}>Đăng xuất</button></div></header>
        <details className="account-panel"><summary>Thông tin tài khoản</summary><dl className="trip-details"><dt>Mã người dùng</dt><dd>{user.id}</dd><dt>Họ tên</dt><dd>{user.name}</dd><dt>Tài khoản</dt><dd>{user.email}</dd><dt>Vai trò</dt><dd>{user.role === 'Driver' ? 'Tài xế' : 'Hành khách'}</dd></dl></details>
        {user.role?.toLowerCase() === 'driver' ? <DriverDashboard key={user.id} user={user} /> : <PassengerDashboard key={user.id} user={user} />}
      </>}
  </main>;
}
