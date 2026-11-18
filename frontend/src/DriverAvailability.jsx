import { useEffect, useState } from 'react';
import { api } from './api';
export default function DriverAvailability() {
  const [driver, setDriver] = useState(null), [error, setError] = useState('');
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
  return <section className="notice" aria-label="Trạng thái nhận chuyến">
    <strong data-testid="driver-availability">{error ? 'Chưa xác nhận được trạng thái tài xế' : !driver ? 'Đang tải trạng thái tài xế…' :
      driver.status === 'AVAILABLE' ? 'Đang chờ chuyến mới' : driver.status === 'BUSY' ? 'Đang bận / đang đồng bộ chuyến' : 'Chưa gửi vị trí để nhận chuyến'}</strong>
    {error && <p>{error}</p>}
    {!error && driver?.location?.coordinates && <p>Vị trí gần nhất đã gửi: {driver.location.coordinates[1]}, {driver.location.coordinates[0]}. Cập nhật vị trí nếu bạn đã di chuyển.</p>}
  </section>;
}
