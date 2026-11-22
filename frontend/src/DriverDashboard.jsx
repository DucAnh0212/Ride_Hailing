import { useEffect, useRef, useState } from 'react';
import { api } from './api';
import DriverAvailability from './DriverAvailability';
import { isActive, tripLabels, useTrips } from './useTrips';
import TripHistory, { TripNotice } from './TripHistory';
import { DISTRICTS, PLACES, findPlaceById, formatPlace, formatVnd } from './places';

const cancelLabels = {
  PASSENGER_CANCELED: 'Hành khách hủy chuyến',
  DRIVER_REJECTED: 'Tài xế từ chối chuyến',
  TIMEOUT_NO_DRIVERS: 'Không tìm thấy tài xế phù hợp',
};

function LocationForm({ userId }) {
  const [placeId, setPlaceId] = useState(PLACES[0].id);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [saved, setSaved] = useState(null);
  const locked = useRef(false), alive = useRef(false), pending = useRef(null);
  useEffect(() => { alive.current = true; return () => { alive.current = false; pending.current?.abort(); }; }, []);

  async function sendCoordinates(lat, lng, label) {
    if (locked.current) return;
    locked.current = true; setBusy(true); setError('');
    pending.current = new AbortController();
    try {
      const response = await api('/api/location', {
        method: 'POST', signal: pending.current.signal,
        body: { driver_id: Number(userId), latitude: lat, longitude: lng },
      });
      if (response.status !== 'success') throw new Error('Chưa xác nhận được cập nhật vị trí');
      if (alive.current) {
        setSaved({ label, at: new Date().toLocaleTimeString('vi-VN') });
        window.dispatchEvent(new Event('driver-location-updated'));
      }
    } catch (err) { if (alive.current) setError(err.message); }
    finally { locked.current = false; if (alive.current) setBusy(false); }
  }

  async function submit(e) {
    e.preventDefault();
    const place = findPlaceById(placeId);
    if (!place) { setError('Vui lòng chọn khu vực hoạt động.'); return; }
    await sendCoordinates(place.lat, place.lng, `${place.name} (${place.district})`);
  }

  function sendDeviceGps() {
    if (locked.current) return;
    if (!navigator.geolocation) { setError('Trình duyệt không hỗ trợ định vị. Hãy chọn địa điểm trong danh sách.'); return; }
    locked.current = true; setBusy(true); setError('');
    navigator.geolocation.getCurrentPosition(position => {
      locked.current = false;
      const { latitude, longitude } = position.coords;
      if (alive.current) sendCoordinates(latitude, longitude, formatPlace(latitude, longitude));
    }, () => {
      locked.current = false;
      if (alive.current) { setBusy(false); setError('Không lấy được GPS thiết bị. Hãy chọn địa điểm trong danh sách.'); }
    }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 });
  }

  return <section className="glass-panel"><h2>Vị trí tài xế</h2><p>Chọn khu vực hoạt động tại Hà Nội để nhận chuyến gần bạn.</p>
    {error && <p role="alert" className="notice error">{error}</p>}
    <form onSubmit={submit}><fieldset disabled={busy} className="booking-fields">
      <label className="form-label">Địa điểm hiện tại
        <select className="form-select" aria-label="Địa điểm hiện tại của tài xế" required value={placeId} onChange={e => setPlaceId(e.target.value)}>
          {DISTRICTS.map(district => (
            <optgroup key={district} label={district}>
              {PLACES.filter(p => p.district === district).map(p => (
                <option key={p.id} value={p.id}>{p.name} — {p.district}</option>
              ))}
            </optgroup>
          ))}
        </select>
      </label>
      <div className="ride-actions">
        <button className="btn btn-primary" type="submit">{busy ? 'Đang xử lý…' : 'Cập nhật vị trí'}</button>
        <button className="btn btn-outline" type="button" onClick={sendDeviceGps}>Dùng GPS thiết bị</button>
      </div>
    </fieldset></form>
    {saved && <p role="status" className="notice">Đã cập nhật tại {saved.label} lúc {saved.at}.</p>}
  </section>;
}

const confirmPrompt = {
  accept: 'Bạn xác nhận nhận chuyến đi này?',
  reject: 'Bạn muốn từ chối chuyến đi này? Trạng thái của bạn sẽ quay về chờ chuyến.',
  start: 'Bạn đã đón hành khách và sẵn sàng bắt đầu?',
  complete: 'Bạn đã đưa hành khách đến điểm đến?',
};

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
    if (confirm.kind === 'accept') await model.accept(trip.tripId);
    else if (confirm.kind === 'reject') { const result = await model.reject(trip.tripId); if (result) setSelected(null); }
    else if (confirm.kind === 'start') await model.start(trip.tripId);
    else { const result = await model.complete(trip.tripId); if (result) setSelected(null); }
    setConfirm(null);
  }

  const confirmValid = Boolean(confirm && trip && confirm.id === trip.tripId && (
    ((confirm.kind === 'accept' || confirm.kind === 'reject') && trip.status === 'MATCHED') ||
    (confirm.kind === 'start' && trip.status === 'ACCEPTED') ||
    (confirm.kind === 'complete' && trip.status === 'STARTED')
  ));

  return <>
    <div className="sync-bar"><span>{model.loading ? 'Đang tải chuyến…' : model.updatedAt ? `Cập nhật lúc ${model.updatedAt.toLocaleTimeString('vi-VN')}` : 'Chưa tải được chuyến'}</span>
      <button className="btn btn-outline" disabled={model.busy || model.loading} onClick={model.refresh}>Tải lại</button></div>
    {model.syncError && <p role="alert" className="notice error">{model.syncError} Trạng thái hiển thị có thể đã cũ.</p>}
    {model.actionError && <p role="alert" className="notice error">{model.actionError}</p>}
    <DriverAvailability />
    <TripNotice model={model} />
    <div className="driver-summary"><span>Chuyến hoàn thành: <strong>{completed.length}</strong></span><span>Tổng cước các chuyến hoàn thành: <strong>{formatVnd(total)}</strong></span></div>
    <div className="dashboard-content"><LocationForm userId={user.id} />
      <section className="glass-panel" aria-label="Chuyến tài xế"><h2>Chuyến được giao</h2>
        {!trip ? <p>{model.loading ? 'Đang tải…' : 'Chưa có chuyến được giao. Khi có chuyến, danh sách sẽ tự cập nhật.'}</p> : <>
          <p className="trip-status" role="status">{tripLabels[trip.status] || trip.status}</p>
          <dl className="trip-details"><dt>Mã chuyến</dt><dd data-testid="trip-id">{trip.tripId}</dd><dt>Mã hành khách</dt><dd>{trip.passengerId}</dd>
            <dt>Điểm đón</dt><dd>{formatPlace(trip.pickupLat, trip.pickupLong)}</dd>
            <dt>Điểm đến</dt><dd>{formatPlace(trip.destLat, trip.destLong)}</dd>
            {trip.fareAmount != null && <><dt>{trip.status === 'COMPLETED' ? 'Cước phí' : 'Giá dự kiến'}</dt><dd>{formatVnd(trip.fareAmount)}</dd></>}
            {trip.paymentStatus === 'PAID_SIMULATED' && <><dt>Thanh toán</dt><dd>Đã thanh toán (giả lập)</dd></>}
            {trip.cancelReason && <><dt>Lý do hủy</dt><dd>{cancelLabels[trip.cancelReason] || trip.cancelReason}</dd></>}
          </dl>
          {!isActive(trip) && <button className="btn btn-outline" onClick={() => { setSelected(null); setConfirm(null); }}>Quay về chờ chuyến</button>}
          {trip.status === 'MATCHED' && <div className="ride-actions">
            <button className="btn btn-primary" disabled={disabled} onClick={() => setConfirm({ id: trip.tripId, kind: 'accept' })}>Nhận chuyến</button>
            <button className="btn btn-danger" disabled={disabled} onClick={() => setConfirm({ id: trip.tripId, kind: 'reject' })}>Từ chối chuyến</button>
          </div>}
          {trip.status === 'ACCEPTED' && <button className="btn btn-primary" disabled={disabled} onClick={() => setConfirm({ id: trip.tripId, kind: 'start' })}>Bắt đầu chuyến</button>}
          {trip.status === 'STARTED' && <button className="btn btn-success" disabled={disabled} onClick={() => setConfirm({ id: trip.tripId, kind: 'complete' })}>Hoàn thành chuyến</button>}
          {confirmValid &&
            <div className="notice"><p>{confirmPrompt[confirm.kind]}</p><div className="ride-actions"><button className={confirm.kind === 'reject' ? 'btn btn-danger' : 'btn btn-primary'} disabled={disabled} onClick={action}>Xác nhận</button><button className="btn btn-outline" disabled={model.busy} onClick={() => setConfirm(null)}>Quay lại</button></div></div>}
        </>}
      </section>
    </div>
    <TripHistory trips={model.trips} selected={trip?.tripId} busy={model.busy} onSelect={id => { setSelected(isActive(model.trips.find(t => t.tripId === id)) ? null : id); setConfirm(null); model.inspect(id); }} />
  </>;
}
