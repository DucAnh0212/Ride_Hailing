import { useState, useEffect } from 'react';



// Auth Component
function Auth({ onLogin }) {
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    role: 'passenger'
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      const endpoint = isLogin ? '/api/auth/login' : '/api/auth/register';
      const payload = isLogin ? { email: formData.email, password: formData.password } : formData;
      
      const response = await fetch(`http://localhost:8000${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        alert(data.message || 'Lỗi xác thực');
        return;
      }
      
      if (data.token) {
        localStorage.setItem('token', data.token);
      }
      onLogin(data.user);
    } catch (error) {
      alert('Không thể kết nối đến server');
      console.error(error);
    }
  };

  return (
    <div className="auth-page" style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column', zIndex: 1000, backgroundImage: 'url("/bg.png")', backgroundSize: '80%', backgroundRepeat: 'no-repeat', backgroundPosition: 'center', backgroundColor: '#6FA4B8' }}>
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)' }}></div>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem 2rem', position: 'absolute', top: 0, left: 0, right: 0, zIndex: 10 }}>
        <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: 'white' }}>
          Ride Hailing System
        </div>
      </header>
      <div className="auth-wrapper" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: '4rem', zIndex: 10 }}>
        <div className="glass-panel auth-container">
          <div className="auth-header">
            <h1>{isLogin ? 'Welcome' : 'Welcome'}</h1>
          </div>
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Phone Number / Email</label>
            <input 
              type="text" 
              className="form-input" 
              value={formData.email}
              onChange={e => setFormData({...formData, email: e.target.value})}
              required
            />
          </div>
          
          <div className="form-group">
            <label className="form-label">Password</label>
            <input 
              type="password" 
              className="form-input" 
              value={formData.password}
              onChange={e => setFormData({...formData, password: e.target.value})}
              required
            />
          </div>

          {!isLogin && (
            <div className="form-group">
              <label className="form-label">I want to be a</label>
              <select 
                className="form-select"
                value={formData.role}
                onChange={e => setFormData({...formData, role: e.target.value})}
              >
                <option value="passenger">Passenger (Ride)</option>
                <option value="driver">Driver (Earn)</option>
              </select>
            </div>
          )}

          <button type="submit" className="btn btn-primary btn-full">
            {isLogin ? 'Sign In' : 'Create Account'}
          </button>
        </form>

        <div className="auth-footer">
          <span style={{ color: 'var(--text-muted)' }}>
            {isLogin ? "Don't have an account? " : "Already have an account? "}
          </span>
          <span 
            className="auth-link"
            onClick={() => setIsLogin(!isLogin)}
          >
            {isLogin ? 'Register now' : 'Sign in'}
          </span>
        </div>
      </div>
    </div>
    </div>
  );
}

// Passenger Dashboard
function PassengerDashboard({ user }) {
  const [pickup, setPickup] = useState('');
  const [destination, setDestination] = useState('');
  const [status, setStatus] = useState('idle'); // idle, finding, found

  const requestRide = (e) => {
    e.preventDefault();
    if (!pickup || !destination) return;
    setStatus('finding');
    
    // Simulate finding driver
    setTimeout(() => {
      setStatus('found');
    }, 3000);
  };

  return (
    <div className="dashboard-content">
      <div className="glass-panel">
        <div className="card-header">
          Request a Ride
        </div>

        {status === 'idle' && (
          <form onSubmit={requestRide} style={{ marginTop: '1.5rem' }}>
            <div className="form-group">
              <label className="form-label">Pickup Location</label>
              <input 
                type="text" 
                className="form-input" 
                placeholder="Current location or address" 
                value={pickup}
                onChange={e => setPickup(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Destination</label>
              <input 
                type="text" 
                className="form-input" 
                placeholder="Where to?" 
                value={destination}
                onChange={e => setDestination(e.target.value)}
                required
              />
            </div>
            <button type="submit" className="btn btn-primary btn-full">
              Find Driver
            </button>
          </form>
        )}

        {status === 'finding' && (
          <div className="finding-state">
            <div className="radar">
              <div className="radar-dot"></div>
              <div className="radar-ring"></div>
              <div className="radar-ring"></div>
            </div>
            <h3>Locating nearby drivers...</h3>
            <p>Please wait while we connect you.</p>
            <button 
              className="btn btn-outline" 
              style={{ marginTop: '1.5rem' }}
              onClick={() => setStatus('idle')}
            >
              Cancel Request
            </button>
          </div>
        )}

        {status === 'found' && (
          <div className="finding-state">
            <div style={{ background: '#10B981', width: '60px', height: '60px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem' }}>
              <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
            </div>
            <h3>Driver Found!</h3>
            <p><strong>Michael T.</strong> is arriving in 4 mins (Toyota Camry - XYZ-1234)</p>
            <button 
              className="btn btn-success btn-full" 
              style={{ marginTop: '1.5rem' }}
              onClick={() => {
                setStatus('idle');
                setPickup('');
                setDestination('');
              }}
            >
              Complete Ride (Demo)
            </button>
          </div>
        )}
      </div>

      <div className="glass-panel">
        <div className="card-header">
          Live Map
        </div>
        <div className="map-placeholder">
          <div className="ping" style={{ top: '40%', left: '30%' }}></div>
          <div className="ping driver" style={{ top: '60%', left: '70%' }}></div>
          <div className="ping driver" style={{ top: '20%', left: '50%' }}></div>
          <span style={{ position: 'absolute', bottom: '10px', right: '10px', fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)' }}>Interactive Map Preview</span>
        </div>
        
        <div className="card" style={{ marginTop: '1rem' }}>
          <h4>Recent Places</h4>
          <p style={{ fontSize: '0.9rem', marginTop: '0.5rem' }}>Central Park, NY</p>
          <p style={{ fontSize: '0.9rem', marginTop: '0.5rem' }}>JFK International Airport</p>
        </div>
      </div>
    </div>
  );
}

// Driver Dashboard
function DriverDashboard({ user }) {
  const [isOnline, setIsOnline] = useState(false);
  const [requests, setRequests] = useState([]);

  // Simulate incoming requests when online
  useEffect(() => {
    let interval;
    if (isOnline) {
      interval = setInterval(() => {
        if (Math.random() > 0.5 && requests.length < 3) {
          const newReq = {
            id: Date.now(),
            pickup: '742 Evergreen Terrace',
            dropoff: 'Springfield Mall',
            price: '$12.50',
            dist: '2.4 mi'
          };
          setRequests(prev => [newReq, ...prev]);
        }
      }, 4000);
    } else {
      setRequests([]); // clear when offline
    }
    return () => clearInterval(interval);
  }, [isOnline, requests]);

  const acceptRequest = (id) => {
    setRequests(requests.filter(r => r.id !== id));
    alert('Ride accepted! Navigating to pickup...');
  };

  const declineRequest = (id) => {
    setRequests(requests.filter(r => r.id !== id));
  };

  return (
    <div className="dashboard-content">
      <div className="glass-panel">
        <div className="card-header" style={{ justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            Driver Status
          </div>
          <div className={`status ${isOnline ? 'status-online' : 'status-offline'}`}>
            <div className="status-dot"></div>
            {isOnline ? 'ONLINE' : 'OFFLINE'}
          </div>
        </div>

        <div style={{ margin: '2rem 0', textAlign: 'center' }}>
          <button 
            className={`btn ${isOnline ? 'btn-danger' : 'btn-success'}`}
            style={{ padding: '1rem 3rem', fontSize: '1.2rem', borderRadius: '50px' }}
            onClick={() => setIsOnline(!isOnline)}
          >
            {isOnline ? 'GO OFFLINE' : 'GO ONLINE'}
          </button>
        </div>

        <div className="card" style={{ marginTop: '1rem', display: 'flex', justifyContent: 'space-around', textAlign: 'center' }}>
          <div>
            <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>Today's Earnings</div>
            <div style={{ fontSize: '1.8rem', fontWeight: '700', color: '#10B981' }}>$142.50</div>
          </div>
          <div style={{ width: '1px', background: 'var(--border-color)' }}></div>
          <div>
            <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>Trips</div>
            <div style={{ fontSize: '1.8rem', fontWeight: '700' }}>8</div>
          </div>
        </div>
      </div>

      <div className="glass-panel">
        <div className="card-header">
          Ride Requests
          {isOnline && <span style={{ fontSize: '0.8rem', background: '#4F46E5', padding: '2px 8px', borderRadius: '12px', marginLeft: 'auto' }}>{requests.length} New</span>}
        </div>

        {!isOnline ? (
          <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-muted)' }}>
            <p style={{ marginTop: '1rem' }}>Go online to receive ride requests.</p>
          </div>
        ) : requests.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-muted)' }}>
            <div className="radar" style={{ margin: '0 auto 1rem' }}>
              <div className="radar-dot" style={{ background: '#10B981' }}></div>
              <div className="radar-ring" style={{ borderColor: '#10B981' }}></div>
              <div className="radar-ring" style={{ borderColor: '#10B981' }}></div>
            </div>
            <p>Searching for nearby riders...</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {requests.map(req => (
              <div key={req.id} className="ride-request" style={{ animation: 'fadeIn 0.4s ease-out' }}>
                <div className="ride-info">
                  <div className="ride-route">
                    <div className="route-point start">{req.pickup}</div>
                    <div className="route-point end">{req.dropoff}</div>
                  </div>
                  <div className="price-tag">{req.price}</div>
                </div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Distance: {req.dist}</div>
                <div className="ride-actions">
                  <button className="btn btn-outline btn-full" onClick={() => declineRequest(req.id)}>Decline</button>
                  <button className="btn btn-primary btn-full" onClick={() => acceptRequest(req.id)}>Accept</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function App() {
  const [user, setUser] = useState(null); // null, or { name, role, email }

  const handleLogout = () => {
    localStorage.removeItem('token');
    setUser(null);
  };

  return (
    <div className="app-container">
      {user && (
        <header className="dashboard-header">
          <div>
            <h1 style={{ fontSize: '1.8rem', margin: 0 }}>Ride Hailing System</h1>
          </div>
          <div className="user-profile">
            <div className="avatar">
              {user.name.charAt(0).toUpperCase()}
            </div>
            <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
              <span style={{ fontWeight: '600' }}>{user.name}</span>
              <button 
                onClick={handleLogout}
                className="btn btn-danger"
                style={{ marginTop: '8px', padding: '0.5rem 1rem' }}
              >
                Logout
              </button>
            </div>
          </div>
        </header>
      )}

      {!user ? (
        <Auth onLogin={setUser} />
      ) : user.role === 'driver' ? (
        <DriverDashboard user={user} />
      ) : (
        <PassengerDashboard user={user} />
      )}
    </div>
  );
}

export default App;
