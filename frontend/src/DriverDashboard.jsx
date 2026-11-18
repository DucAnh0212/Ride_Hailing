import { useEffect, useRef, useState } from 'react';
import { api } from './api';
import DriverAvailability from './DriverAvailability';
import { isActive, tripLabels, useTrips } from './useTrips';
import TripHistory, { TripNotice } from './TripHistory';
const money = amount => new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
function LocationForm({ userId }) {
  const [lat, setLat] = useState(''), [lng, setLng] = useState('');
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [saved, setSaved] = useState(null);
  const locked = useRef(false), alive = useRef(false), pending = useRef(null);
  function cleanup() { alive.current = false; pending.current?.abort(); }
  useEffect(() => { alive.current = true; return cleanup; }, []);
  function gps() {
    if (locked.current) return;
    if (!navigator.geolocation) { setError('Trình duyệt không hỗ trợ định vị. Bạn có thể nhập tọa độ.'); return; }
    locked.current = true; setBusy(true); setError('');
    navigator.geolocation.getCurrentPosition(position => {
      locked.current = false;
      if (alive.current) { setLat(String(position.coords.latitude)); setLng(String(position.coords.longitude)); setBusy(false); }
    }, () => {
      locked.current = false;
      if (alive.current) { setBusy(false); setError('Không lấy được vị trí. Hãy cấp quyền định vị hoặc nhập tọa độ thủ công.'); }
    }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 });
  }
  async function submit(e) {
    e.preventDefault(); if (locked.current) return;
    if (!lat.trim() || !lng.trim() || !Number.isFinite(Number(lat)) || !Number.isFinite(Number(lng)) || Math.abs(Number(lat)) > 90 || Math.abs(Number(lng)) > 180) {
      setError('Tọa độ không hợp lệ.'); return;
    }
    locked.current = true; setBusy(true); setError('');
    pending.current = new AbortController();
    try {
      const response = await api('/api/location', { method: 'POST', signal: pending.current.signal,
        body: { driver_id: Number(userId), latitude: Number(lat), longitude: Number(lng) } });
      if (response.status !== 'success') throw new Error('Chưa xác nhận được cập nhật vị trí');
      if (alive.current) { setSaved({ lat, lng, at: new Date().toLocaleTimeString('vi-VN') }); window.dispatchEvent(new Event('driver-location-updated')); }
    } catch (err) { if (alive.current) setError(err.message); }
    finally { locked.current = false; if (alive.current) setBusy(false); }
  }
  return <section className="glass-panel"><h2>Vị trí tài xế</h2><p>Gửi vị trí hiện tại để hệ thống tìm các chuyến gần bạn.</p>
    {error && <p role="alert" className="notice error">{error}</p>}
    <form onSubmit={submit}><fieldset disabled={busy} className="booking-fields"><div className="coordinate-grid">
      <label className="form-label">Vĩ độ tài xế<input className="form-input" required type="number" step="any" min="-90" max="90" value={lat} onChange={e => setLat(e.target.value)} /></label>
      <label className="form-label">Kinh độ tài xế<input className="form-input" required type="number" step="any" min="-180" max="180" value={lng} onChange={e => setLng(e.target.value)} /></label>
    </div><div className="ride-actions"><button className="btn btn-outline" type="button" onClick={gps}>Lấy vị trí thiết bị</button><button className="btn btn-primary" type="submit">{busy ? 'Đang xử lý…' : 'Gửi vị trí'}</button></div></fieldset></form>
    {saved && <p role="status" className="notice">Đã gửi vị trí {saved.lat}, {saved.lng} lúc {saved.at}.</p>}
  </section>;
}
export default function DriverDashboard({ user }) {
  const model = useTrips(user.id, 'Driver');
  const [selected, setSelected] = useState(null), [confirm, setConfirm] = useState(null);
  const active = model.trips.filter(isActive);
  const trip = model.trips.find(t => t.tripId === selected) || active[0];
  const completed = model.trips.filter(t => t.status === 'COMPLETED');
  const total = completed.reduce((sum, t) => sum + (Number(t.fareAmount) || 0), 0);
  const disabled = model.busy || model.loading || !!model.syncError;
  async function action() {
    if (!confirm || confirm.id !== trip?.tripId) return;
    if (confirm.kind === 'start') await model.start(trip.tripId); else { const result = await model.complete(trip.tripId); if (result) setSelected(null); }
    setConfirm(null);
  }
  return <>
    <div className="sync-bar"><span>{model.loading ? 'Đang tải chuyến…' : model.updatedAt ? `Cập nhật lúc ${model.updatedAt.toLocaleTimeString('vi-VN')}` : 'Chưa tải được chuyến'}</span>
      <button className="btn btn-outline" disabled={model.busy || model.loading} onClick={model.refresh}>Tải lại</button></div>
    {model.syncError && <p role="alert" className="notice error">{model.syncError} Trạng thái hiển thị có thể đã cũ.</p>}
    {model.actionError && <p role="alert" className="notice error">{model.actionError}</p>}
    <DriverAvailability />
    <TripNotice model={model} />
    <div className="driver-summary"><span>Chuyến hoàn thành: <strong>{completed.length}</strong></span><span>Tổng cước các chuyến hoàn thành: <strong>{money(total)}</strong></span></div>
    <div className="dashboard-content"><LocationForm userId={user.id} />
      <section className="glass-panel" aria-label="Chuyến tài xế"><h2>Chuyến được giao</h2>
        {!trip ? <p>{model.loading ? 'Đang tải…' : 'Chưa có chuyến được giao. Khi có chuyến, danh sách sẽ tự cập nhật.'}</p> : <>
          <p className="trip-status" role="status">{tripLabels[trip.status] || trip.status}</p>
          <dl className="trip-details"><dt>Mã chuyến</dt><dd data-testid="trip-id">{trip.tripId}</dd><dt>Mã hành khách</dt><dd>{trip.passengerId}</dd>
            <dt>Điểm đón</dt><dd>{trip.pickupLat}, {trip.pickupLong}</dd><dt>Điểm đến</dt><dd>{trip.destLat}, {trip.destLong}</dd>
            {trip.fareAmount != null && <><dt>Cước phí</dt><dd>{money(trip.fareAmount)}</dd></>}
            {trip.paymentStatus === 'PAID_SIMULATED' && <><dt>Thanh toán</dt><dd>Đã thanh toán (giả lập)</dd></>}
            {trip.cancelReason && <><dt>Lý do hủy</dt><dd>{trip.cancelReason === 'PASSENGER_CANCELED' ? 'Hành khách hủy chuyến' : trip.cancelReason}</dd></>}
          </dl>
          {!isActive(trip) && <button className="btn btn-outline" onClick={() => { setSelected(null); setConfirm(null); }}>Quay về chờ chuyến</button>}
          {trip.status === 'ACCEPTED' && <button className="btn btn-primary" disabled={disabled} onClick={() => setConfirm({ id: trip.tripId, kind: 'start' })}>Bắt đầu chuyến</button>}
          {trip.status === 'STARTED' && <button className="btn btn-success" disabled={disabled} onClick={() => setConfirm({ id: trip.tripId, kind: 'complete' })}>Hoàn thành chuyến</button>}
          {confirm?.id === trip.tripId && ((confirm.kind === 'start' && trip.status === 'ACCEPTED') || (confirm.kind === 'complete' && trip.status === 'STARTED')) &&
            <div className="notice"><p>{confirm.kind === 'start' ? 'Bạn đã đón hành khách và sẵn sàng bắt đầu?' : 'Bạn đã đưa hành khách đến điểm đến?'}</p><div className="ride-actions"><button className="btn btn-primary" disabled={disabled} onClick={action}>Xác nhận</button><button className="btn btn-outline" disabled={model.busy} onClick={() => setConfirm(null)}>Quay lại</button></div></div>}
        </>}
      </section>
    </div>
    <TripHistory trips={model.trips} selected={trip?.tripId} busy={model.busy} onSelect={id => { setSelected(isActive(model.trips.find(t => t.tripId === id)) ? null : id); setConfirm(null); model.inspect(id); }} />
  </>;
}
