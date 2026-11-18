import { useState } from 'react';
import { isActive, useTrips } from './useTrips';
import TripHistory, { TripNotice } from './TripHistory';
const labels = { PENDING: 'Đang tìm tài xế', ACCEPTED: 'Đã có tài xế', STARTED: 'Đang di chuyển', COMPLETED: 'Đã hoàn thành', CANCELED: 'Đã hủy' };
const places = [
  { name: 'Hồ Hoàn Kiếm', lat: 21.0285, lng: 105.8542 },
  { name: 'Công viên Thống Nhất', lat: 21.0118, lng: 105.8502 },
  { name: 'Văn Miếu', lat: 21.0278, lng: 105.8355 },
];
function Point({ title, value, onChange }) {
  return <fieldset className="point-fields"><legend>{title}</legend>
    <label className="form-label">Địa điểm mẫu
      <select className="form-select" aria-label={`${title} địa điểm mẫu`} value="" onChange={e => {
        const point = places[Number(e.target.value)]; if (point) onChange({ lat: String(point.lat), lng: String(point.lng) });
      }}><option value="" disabled>Chọn địa điểm hoặc nhập tọa độ</option>{places.map((p, i) => <option key={p.name} value={i}>{p.name}</option>)}</select>
    </label>
    <div className="coordinate-grid">{[['lat', 'Vĩ độ', -90, 90], ['lng', 'Kinh độ', -180, 180]].map(([key, name, min, max]) =>
      <label key={key} className="form-label">{name}<input className="form-input" aria-label={`${title} ${name}`} type="number" step="any" min={min} max={max} required
        value={value[key]} onChange={e => onChange({ ...value, [key]: e.target.value })} /></label>)}</div>
  </fieldset>;
}
export default function PassengerDashboard({ user }) {
  const model = useTrips(user.id);
  const [pickup, setPickup] = useState({ lat: '', lng: '' });
  const [destination, setDestination] = useState({ lat: '', lng: '' });
  const [selected, setSelected] = useState(null);
  const [confirmId, setConfirmId] = useState(null);
  const [validation, setValidation] = useState('');
  const active = model.trips.filter(isActive);
  const trip = model.trips.find(t => t.tripId === selected) || active[0] || model.trips[0];
  const blocked = model.loading || model.busy || !!model.syncError || !model.updatedAt || model.uncertain || active.length > 0;
  async function book(e) {
    e.preventDefault(); if (blocked) return;
    const values = [pickup.lat, pickup.lng, destination.lat, destination.lng];
    if (values.some(v => !String(v).trim() || !Number.isFinite(Number(v))) ||
      Math.abs(Number(pickup.lat)) > 90 || Math.abs(Number(destination.lat)) > 90 ||
      Math.abs(Number(pickup.lng)) > 180 || Math.abs(Number(destination.lng)) > 180) {
      setValidation('Vui lòng nhập tọa độ hợp lệ.'); return;
    }
    if (Number(pickup.lat) === Number(destination.lat) && Number(pickup.lng) === Number(destination.lng)) { setValidation('Điểm đón và điểm đến phải khác nhau.'); return; }
    setValidation('');
    const result = await model.create({ pickupLat: Number(pickup.lat), pickupLong: Number(pickup.lng),
      destLat: Number(destination.lat), destLong: Number(destination.lng), vehicleType: 'MOTORBIKE' });
    if (result) setSelected(result.tripId);
  }
  return <>
    <div className="sync-bar"><span>{model.loading ? 'Đang tải chuyến đi…' : model.updatedAt ? `Cập nhật lúc ${model.updatedAt.toLocaleTimeString('vi-VN')}` : 'Chưa tải được chuyến đi'}</span>
      <button className="btn btn-outline" disabled={model.busy || model.loading} onClick={model.refresh}>Tải lại</button></div>
    {model.syncError && <p role="alert" className="notice error">{model.syncError} Trạng thái hiển thị có thể đã cũ; hệ thống sẽ thử tải lại.</p>}
    {(model.actionError || validation) && <p role="alert" className="notice error">{validation || model.actionError}</p>}
    {model.uncertain && <div className="notice" role="status"><p>Vui lòng kiểm tra các chuyến bên dưới. Không tự động gửi lại yêu cầu đặt xe.</p>
      {active.length === 0 && model.updatedAt && !model.syncError && !model.busy && <button className="btn btn-outline" onClick={model.acknowledge}>Đã kiểm tra, cho phép đặt lại</button>}</div>}
    <TripNotice model={model} />
    <div className="dashboard-content">
      <section className="glass-panel"><h2>Đặt xe</h2><p>Chọn điểm mẫu hoặc nhập tọa độ điểm đón và điểm đến. Loại xe: xe máy.</p>
        {active.length > 0 && <p className="notice">Bạn có {active.length} chuyến đang diễn ra. Hãy theo dõi hoặc hủy chuyến trước khi đặt mới.</p>}
        <form onSubmit={book}><fieldset disabled={blocked} className="booking-fields">
          <Point title="Điểm đón" value={pickup} onChange={setPickup} />
          <Point title="Điểm đến" value={destination} onChange={setDestination} />
          <button className="btn btn-primary btn-full" type="submit">{model.busy ? 'Đang xử lý…' : 'Đặt xe'}</button>
        </fieldset></form>
      </section>
      <section className="glass-panel" aria-label="Theo dõi chuyến"><h2>Chuyến đi của bạn</h2>
        {!trip ? <p>{model.loading ? 'Đang tải…' : 'Chưa có chuyến đi.'}</p> : <>
          <p className="trip-status" role="status">{labels[trip.status] || trip.status}</p>
          <dl className="trip-details"><dt>Mã chuyến</dt><dd data-testid="trip-id">{trip.tripId}</dd>
            <dt>Điểm đón</dt><dd>{trip.pickupLat}, {trip.pickupLong}</dd>
            <dt>Điểm đến</dt><dd>{trip.destLat}, {trip.destLong}</dd>
            <dt>Tài xế</dt><dd>{trip.driverId || 'Chưa được phân công'}</dd>
            {trip.fareAmount != null && <><dt>Cước phí</dt><dd>{new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(trip.fareAmount)}</dd></>}
            {trip.paymentStatus === 'PAID_SIMULATED' && <><dt>Thanh toán</dt><dd>Đã thanh toán (giả lập)</dd></>}
            {trip.cancelReason && <><dt>Lý do hủy</dt><dd>{trip.cancelReason === 'TIMEOUT_NO_DRIVERS' ? 'Không tìm thấy tài xế phù hợp' : trip.cancelReason === 'PASSENGER_CANCELED' ? 'Hành khách hủy chuyến' : trip.cancelReason}</dd></>}
          </dl>
          {isActive(trip) && (confirmId !== trip.tripId ? <button className="btn btn-danger" disabled={model.busy || !!model.syncError} onClick={() => setConfirmId(trip.tripId)}>Hủy chuyến</button> :
            <div className="notice"><p>Bạn muốn hủy chuyến này?</p><div className="ride-actions">
              <button className="btn btn-danger" disabled={model.busy || !!model.syncError} onClick={async () => { await model.cancel(trip.tripId); setConfirmId(null); }}>Xác nhận hủy</button>
              <button className="btn btn-outline" disabled={model.busy} onClick={() => setConfirmId(null)}>Giữ chuyến</button>
            </div></div>)}
        </>}
      </section>
    </div>
    <TripHistory trips={model.trips} selected={trip?.tripId} busy={model.busy} onSelect={id => { setSelected(id); setConfirmId(null); model.inspect(id); }} />
  </>;
}
