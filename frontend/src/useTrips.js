import { useEffect, useRef, useState } from 'react';
import { api } from './api';
export const isActive = trip => ['PENDING', 'MATCHED', 'ACCEPTED', 'STARTED'].includes(trip?.status);
export const tripLabels = {
  PENDING: 'Đang tìm tài xế',
  MATCHED: 'Chờ tài xế xác nhận',
  ACCEPTED: 'Đã có tài xế nhận chuyến',
  STARTED: 'Đang di chuyển',
  COMPLETED: 'Đã hoàn thành',
  CANCELED: 'Đã hủy',
};
export function useTrips(userId, role = 'Rider') {
  const [trips, setTrips] = useState([]), [loading, setLoading] = useState(true);
  const [syncError, setSyncError] = useState(''), [actionError, setActionError] = useState('');
  const [notice, setNotice] = useState(''), [busy, setBusy] = useState(false);
  const key = `uncertain-booking:${userId}`;
  const [uncertain, setUncertain] = useState(() => sessionStorage.getItem(key) === '1');
  const [updatedAt, setUpdatedAt] = useState(null);
  const gate = useRef(false), epoch = useRef(0), mounted = useRef(false), snapshot = useRef(null), reschedule = useRef(null);
  const driver = role.toLowerCase() === 'driver';
  function owned(t) { return String(driver ? t.driverId : t.passengerId) === String(userId); }
  function markUncertain(value) {
    if (value) sessionStorage.setItem(key, '1'); else sessionStorage.removeItem(key);
    setUncertain(value);
  }
  function acceptSnapshot(data) {
    const sorted = data.filter(owned).sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
    if (snapshot.current) {
      const changes = sorted.filter(t => snapshot.current.get(t.tripId) !== t.status);
      if (changes.length) setNotice(changes.map(t => `${t.tripId}: ${tripLabels[t.status] || t.status}`).join(' · '));
    }
    snapshot.current = new Map(sorted.map(t => [t.tripId, t.status]));
    setTrips(sorted); setUpdatedAt(new Date());
  }
  async function refresh(signal) {
    if (gate.current) return;
    const version = ++epoch.current;
    try {
      const data = await api('/api/trips', { signal });
      if (!Array.isArray(data)) throw new Error('Danh sách chuyến không hợp lệ');
      if (!mounted.current || version !== epoch.current) return;
      acceptSnapshot(data); setSyncError(''); setLoading(false);
    } catch (error) {
      if (mounted.current && !signal?.aborted && version === epoch.current) { setSyncError(error.message); setLoading(false); }
    }
  }
  function invalidate() { ++epoch.current; }
  function pollDelay() {
    return snapshot.current && [...snapshot.current.values()].some(s => ['PENDING', 'MATCHED', 'ACCEPTED', 'STARTED'].includes(s)) ? 2000 : driver ? 5000 : 15000;
  }
  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController(); let timer;
    async function poll() {
      clearTimeout(timer);
      if (!document.hidden) await refresh(controller.signal);
      if (!controller.signal.aborted) timer = setTimeout(poll, pollDelay());
    }
    const visibility = () => { if (!document.hidden) poll(); };
    reschedule.current = () => { clearTimeout(timer); timer = setTimeout(poll, pollDelay()); };
    document.addEventListener('visibilitychange', visibility);
    poll();
    return () => { mounted.current = false; invalidate(); controller.abort(); clearTimeout(timer); document.removeEventListener('visibilitychange', visibility); };
    // The dashboard is keyed by account; polling reads the latest snapshot via refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, role]);
  async function mutate(path, body, creating) {
    if (gate.current) return;
    gate.current = true; ++epoch.current; setBusy(true); setActionError('');
    if (creating) markUncertain(true);
    try {
      const trip = await api(path, { method: creating ? 'POST' : 'PUT', body });
      if (!trip.tripId || !trip.status || !owned(trip)) throw new Error('Chưa xác nhận được kết quả thao tác');
      if (mounted.current) {
        setTrips(current => [trip, ...current.filter(t => t.tripId !== trip.tripId)]);
        setNotice(`${trip.tripId}: ${tripLabels[trip.status] || trip.status}`);
        if (creating) markUncertain(false);
      }
      return trip;
    } catch (error) {
      if (mounted.current) {
        setActionError(creating && (!error.status || error.status >= 500)
          ? 'Chưa xác nhận được việc tạo chuyến. Hãy kiểm tra danh sách trước khi đặt lại để tránh trùng chuyến.' : error.message);
        if (creating && error.status >= 400 && error.status < 500) markUncertain(false);
      }
    } finally {
      gate.current = false; ++epoch.current;
      if (mounted.current) { setBusy(false); await refresh(); reschedule.current?.(); }
    }
  }
  async function inspect(id) {
    if (gate.current) return;
    const version = ++epoch.current;
    try {
      const trip = await api(`/api/trips/${encodeURIComponent(id)}`);
      if (!owned(trip)) throw new Error('Bạn không có quyền xem chuyến này');
      if (mounted.current && version === epoch.current) {
        setTrips(current => current.map(t => t.tripId === id ? trip : t)); setActionError('');
      }
    } catch (error) { if (mounted.current && version === epoch.current) setActionError(error.message); }
  }
  return { trips, loading, busy, uncertain, syncError, actionError, updatedAt, notice, inspect,
    dismissNotice: () => setNotice(''), refresh: () => refresh(), acknowledge: () => { markUncertain(false); setActionError(''); },
    create: body => mutate('/api/trips', { ...body, passengerId: String(userId) }, true),
    accept: id => mutate(`/api/trips/${encodeURIComponent(id)}/accept`, undefined, false),
    reject: id => mutate(`/api/trips/${encodeURIComponent(id)}/reject`, { reason: 'DRIVER_REJECTED' }, false),
    cancel: id => mutate(`/api/trips/${encodeURIComponent(id)}/cancel`, { reason: 'PASSENGER_CANCELED' }, false),
    start: id => mutate(`/api/trips/${encodeURIComponent(id)}/start`, undefined, false),
    complete: id => mutate(`/api/trips/${encodeURIComponent(id)}/complete`, undefined, false) };
}
