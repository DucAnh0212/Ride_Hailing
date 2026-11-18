import { useState } from 'react';
import { isActive, tripLabels } from './useTrips';
export function TripNotice({ model }) {
  return model.notice ? <div className="notice sync-bar"><p role="status">{model.notice}</p><button className="btn btn-outline" onClick={model.dismissNotice} aria-label="Đóng thông báo">Đóng</button></div> : null;
}
export default function TripHistory({ trips, selected, onSelect, busy }) {
  const [filter, setFilter] = useState('all');
  const shown = trips.filter(t => filter === 'all' || (filter === 'active' ? isActive(t) : !isActive(t)));
  return <section className="glass-panel trip-history"><h2>Danh sách chuyến</h2>
    <p>Chuyến đang hoạt động tự cập nhật mỗi 2 giây. Khi rời tab, cập nhật tạm dừng và tiếp tục khi quay lại.</p>
    <div className="ride-actions history-filters" aria-label="Lọc chuyến">{[['all', 'Tất cả'], ['active', 'Đang hoạt động'], ['history', 'Lịch sử']].map(([value, label]) =>
      <button key={value} className="btn btn-outline" aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}</div>
    {!shown.length && <p>Không có chuyến trong danh sách này.</p>}
    <ul>{shown.map(t => <li key={t.tripId}><button className="btn btn-outline" disabled={busy} aria-pressed={selected === t.tripId} onClick={() => onSelect(t.tripId)}>{t.tripId} — {tripLabels[t.status] || t.status}</button></li>)}</ul>
  </section>;
}
