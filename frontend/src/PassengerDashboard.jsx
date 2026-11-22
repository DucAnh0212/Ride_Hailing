import { useState } from 'react';
import { isActive, tripLabels, useTrips } from './useTrips';
import TripHistory, { TripNotice } from './TripHistory';
import { DISTRICTS, PLACES, estimateFare, findPlaceById, formatPlace, formatVnd } from './places';

const cancelLabels = {
  TIMEOUT_NO_DRIVERS: 'Không tìm thấy tài xế phù hợp',
  PASSENGER_CANCELED: 'Hành khách hủy chuyến',
  DRIVER_REJECTED: 'Tài xế đã từ chối chuyến',
};

function AddressSelect({ title, value, onChange }) {
  return <label className="form-label">{title}
    <select className="form-select" aria-label={title} required value={value} onChange={e => onChange(e.target.value)}>
      <option value="" disabled>Chọn địa điểm tại Hà Nội…</option>
      {DISTRICTS.map(district => (
        <optgroup key={district} label={district}>
          {PLACES.filter(p => p.district === district).map(p => (
            <option key={p.id} value={p.id}>{p.name} — {p.district}</option>
          ))}
        </optgroup>
      ))}
    </select>
  </label>;
}

export default function PassengerDashboard({ user }) {
  const model = useTrips(user.id);
  const [pickupId, setPickupId] = useState('');
  const [destId, setDestId] = useState('');
  const [selected, setSelected] = useState(null);
  const [confirmId, setConfirmId] = useState(null);
  const [validation, setValidation] = useState('');

  const pickup = findPlaceById(pickupId);
  const destination = findPlaceById(destId);
  const estimate = pickup && destination && pickup.id !== destination.id ? estimateFare(pickup, destination) : null;

  const active = model.trips.filter(isActive);
  const trip = model.trips.find(t => t.tripId === selected) || active[0] || model.trips[0];
  const blocked = model.loading || model.busy || !!model.syncError || !model.updatedAt || model.uncertain || active.length > 0;

  async function book(e) {
    e.preventDefault(); if (blocked) return;
    if (!pickup || !destination) { setValidation('Vui lòng chọn cả điểm đón và điểm đến.'); return; }
    if (pickup.id === destination.id) { setValidation('Điểm đón và điểm đến phải khác nhau.'); return; }
    setValidation('');
    const result = await model.create({
      pickupLat: pickup.lat, pickupLong: pickup.lng,
      destLat: destination.lat, destLong: destination.lng,
      vehicleType: 'MOTORBIKE',
    });
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
      <section className="glass-panel"><h2>Đặt xe</h2><p>Chọn địa điểm đón và điểm đến trong khu vực nội thành Hà Nội (7 quận hoạt động). Loại xe: xe máy.</p>
        {active.length > 0 && <p className="notice">Bạn có {active.length} chuyến đang diễn ra. Hãy theo dõi hoặc hủy chuyến trước khi đặt mới.</p>}
        <form onSubmit={book}><fieldset disabled={blocked} className="booking-fields">
          <AddressSelect title="Điểm đón" value={pickupId} onChange={id => { setPickupId(id); setValidation(''); }} />
          <AddressSelect title="Điểm đến" value={destId} onChange={id => { setDestId(id); setValidation(''); }} />
          {estimate && <div className="notice" role="status" data-testid="fare-estimate">
            <strong>Giá dự kiến: {formatVnd(estimate.fareAmount)}</strong>
            <p>Quãng đường ước tính ~{estimate.distanceKm} km (15.000 ₫ mở cửa + 10.000 ₫/km).</p>
          </div>}
          <button className="btn btn-primary btn-full" type="submit">{model.busy ? 'Đang xử lý…' : 'Đặt xe'}</button>
        </fieldset></form>
      </section>
      <section className="glass-panel" aria-label="Theo dõi chuyến"><h2>Chuyến đi của bạn</h2>
        {!trip ? <p>{model.loading ? 'Đang tải…' : 'Chưa có chuyến đi.'}</p> : <>
          <p className="trip-status" role="status">{tripLabels[trip.status] || trip.status}</p>
          <dl className="trip-details"><dt>Mã chuyến</dt><dd data-testid="trip-id">{trip.tripId}</dd>
            <dt>Điểm đón</dt><dd>{formatPlace(trip.pickupLat, trip.pickupLong)}</dd>
            <dt>Điểm đến</dt><dd>{formatPlace(trip.destLat, trip.destLong)}</dd>
            <dt>Tài xế</dt><dd>{trip.driverId || 'Chưa được phân công'}</dd>
            {trip.fareAmount != null && <><dt>{trip.status === 'COMPLETED' ? 'Cước phí' : 'Giá dự kiến'}</dt><dd>{formatVnd(trip.fareAmount)}</dd></>}
            {trip.paymentStatus === 'PAID_SIMULATED' && <><dt>Thanh toán</dt><dd>Đã thanh toán (giả lập)</dd></>}
            {trip.cancelReason && <><dt>Lý do hủy</dt><dd>{cancelLabels[trip.cancelReason] || trip.cancelReason}</dd></>}
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
