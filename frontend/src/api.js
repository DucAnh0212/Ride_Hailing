const configured = import.meta.env.VITE_API_GATEWAY_URL;
export const API_BASE_URL = configured || `${window.location.protocol}//${window.location.hostname}:3000`;
export class ApiError extends Error {
  constructor(message, status = 0) { super(message); this.status = status; }
}
export async function api(path, { method = 'GET', body, signal, authenticated = true } = {}) {
  const token = authenticated ? localStorage.getItem('token') : null;
  try {
    const response = await fetch(API_BASE_URL + path, {
      method, signal: AbortSignal.any([AbortSignal.timeout(10000), ...(signal ? [signal] : [])]),
      headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await response.json().catch(() => null);
    if (response.status === 401 && token && localStorage.getItem('token') === token) {
      localStorage.removeItem('token'); window.dispatchEvent(new Event('session-expired'));
    }
    if (!response.ok) throw new ApiError(data?.message || `Yêu cầu thất bại (${response.status})`, response.status);
    if (data === null) throw new ApiError('Phản hồi máy chủ không hợp lệ');
    return data;
  } catch (error) {
    if (signal?.aborted) throw error;
    if (error instanceof ApiError) throw error;
    throw new ApiError('Không thể kết nối hoặc máy chủ phản hồi quá lâu. Vui lòng kiểm tra lại.');
  }
}
