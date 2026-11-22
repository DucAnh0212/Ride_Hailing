import { useEffect, useState } from 'react';
import { api } from './api';
import { formatPlace } from './places';
export default function DriverAvailability() {
  const [driver, setDriver] = useState(null), [error, setError] = useState(''), [toggling, setToggling] = useState(false);
  useEffect(() => {
    const controller = new AbortController(); let timer, generation = 0;
    async function poll() {
      clearTimeout(timer); const current = ++generation;
      if (!document.hidden) {
        try {
          const value = await api('/api/location/me', { signal: controller.signal });
          if (!['AVAILABLE', 'BUSY', 'OFFLINE'].includes(value.status)) throw new Error('Trạng thái tài xế không hợp lệ');
          if (!controller.signal.aborted && current === generation) { setDriver(value); setError(''); }
        } catch (err) { if (!controller.signal.aborted && current === generation) setError(err.message); }
      }
      if (!controller.signal.aborted && current === generation) timer = setTimeout(poll, 2000);
    }
    const wake = () => { if (!document.hidden) poll(); };
    window.addEventListener('driver-location-updated', wake); document.addEventListener('visibilitychange', wake);
    poll();
    return () => { controller.abort(); clearTimeout(timer); window.removeEventListener('driver-location-updated', wake); document.removeEventListener('visibilitychange', wake); };
  }, []);
  async function toggleStatus() {
    if (!driver || driver.status === 'BUSY' || !driver.location || toggling) return;
    const next = driver.status === 'AVAILABLE' ? 'OFFLINE' : 'AVAILABLE';
    setToggling(true); setError('');
    try {
      await api('/api/location/status', { method: 'PUT', body: { status: next } });
      setDriver(current => current ? { ...current, status: next } : current);
      window.dispatchEvent(new Event('driver-location-updated'));
    } catch (err) { setError(err.message); }
    finally { setToggling(false); }
  }
  const canToggle = !toggling && driver?.location && (driver.status === 'AVAILABLE' || driver.status === 'OFFLINE');
  return <section className="notice" aria-label="Trạng thái nhận chuyến">
    <div className="sync-bar">
      <strong data-testid="driver-availability">{error ? 'Chưa xác nhận được trạng thái tài xế' : !driver ? 'Đang tải trạng thái tài xế…' :
        driver.status === 'AVAILABLE' ? 'Đang chờ chuyến mới (Online)' : driver.status === 'BUSY' ? 'Đang bận / đang giữ chuyến' :
          driver.location ? 'Tạm nghỉ nhận chuyến (Offline)' : 'Chưa gửi vị trí để nhận chuyến'}</strong>
      {driver?.location && driver.status !== 'BUSY' && <button className="btn btn-outline" type="button" disabled={!canToggle} onClick={toggleStatus}>
        {toggling ? 'Đang cập nhật…' : driver.status === 'AVAILABLE' ? 'Chuyển sang Offline' : 'Bật Online nhận chuyến'}
      </button>}
    </div>
    {error && <p role="alert">{error}</p>}
    {!error && driver?.location?.coordinates && <p>Vị trí hiện tại: {formatPlace(driver.location.coordinates[1], driver.location.coordinates[0])}. Cập nhật vị trí nếu bạn đã di chuyển.</p>}
  </section>;
}
