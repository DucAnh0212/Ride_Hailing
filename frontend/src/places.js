// Preset landmarks strictly inside the driver_simulator Hanoi operating zone:
// lat in [20.9800, 21.0600], lng in [105.7700, 105.8700]
export const PLACES = [
  { id: 'hk-ho-guom', district: 'Quận Hoàn Kiếm', name: 'Hồ Hoàn Kiếm', lat: 21.0285, lng: 105.8542 },
  { id: 'hk-nha-hat-lon', district: 'Quận Hoàn Kiếm', name: 'Nhà Hát Lớn Hà Nội', lat: 21.0243, lng: 105.8576 },
  { id: 'hk-ga-ha-noi', district: 'Quận Hoàn Kiếm', name: 'Ga Hà Nội', lat: 21.0245, lng: 105.8412 },
  { id: 'bd-lang-bac', district: 'Quận Ba Đình', name: 'Lăng Chủ tịch Hồ Chí Minh', lat: 21.0368, lng: 105.8347 },
  { id: 'bd-lotte', district: 'Quận Ba Đình', name: 'Lotte Center Liễu Giai', lat: 21.0319, lng: 105.8126 },
  { id: 'dd-van-mieu', district: 'Quận Đống Đa', name: 'Văn Miếu - Quốc Tử Giám', lat: 21.0278, lng: 105.8355 },
  { id: 'dd-vincom-pnt', district: 'Quận Đống Đa', name: 'Vincom Phạm Ngọc Thạch', lat: 21.0065, lng: 105.8315 },
  { id: 'hbt-cv-thong-nhat', district: 'Quận Hai Bà Trưng', name: 'Công viên Thống Nhất', lat: 21.0118, lng: 105.8502 },
  { id: 'hbt-bach-khoa', district: 'Quận Hai Bà Trưng', name: 'Đại học Bách Khoa Hà Nội', lat: 21.0046, lng: 105.8431 },
  { id: 'hbt-times-city', district: 'Quận Hai Bà Trưng', name: 'Times City Minh Khai', lat: 20.9954, lng: 105.8678 },
  { id: 'cg-cv-cau-giay', district: 'Quận Cầu Giấy', name: 'Công viên Cầu Giấy', lat: 21.0289, lng: 105.7905 },
  { id: 'cg-my-dinh', district: 'Quận Cầu Giấy', name: 'Bến xe Mỹ Đình', lat: 21.0284, lng: 105.7785 },
  { id: 'cg-dhqg', district: 'Quận Cầu Giấy', name: 'Đại học Quốc Gia Xuân Thủy', lat: 21.0378, lng: 105.7826 },
  { id: 'tx-royal-city', district: 'Quận Thanh Xuân', name: 'Royal City Nguyễn Trãi', lat: 21.0029, lng: 105.8154 },
  { id: 'tx-nga-tu-so', district: 'Quận Thanh Xuân', name: 'Ngã Tư Sở', lat: 21.0036, lng: 105.8206 },
  { id: 'th-tran-quoc', district: 'Quận Tây Hồ', name: 'Chùa Trấn Quốc - Hồ Tây', lat: 21.0479, lng: 105.8368 },
];

export const DISTRICTS = [...new Set(PLACES.map(p => p.district))];

export const findPlaceById = id => PLACES.find(p => p.id === id) || null;

export function formatPlace(lat, lng) {
  if (lat == null || lng == null) return 'Chưa xác định';
  const match = PLACES.find(p => Math.abs(p.lat - Number(lat)) < 0.0005 && Math.abs(p.lng - Number(lng)) < 0.0005);
  return match ? `${match.name} (${match.district})` : `Vị trí GPS (${Number(lat).toFixed(4)}, ${Number(lng).toFixed(4)})`;
}

// Mirrors booking_service FareCalculationService (15,000 VND base + 10,000 VND/km Haversine)
const EARTH_RADIUS_KM = 6371.0;
const BASE_FARE = 15000.0;
const RATE_PER_KM = 10000.0;

export function estimateFare(pickup, destination) {
  if (!pickup || !destination) return null;
  const toRad = deg => (deg * Math.PI) / 180;
  const dLat = toRad(destination.lat - pickup.lat);
  const dLng = toRad(destination.lng - pickup.lng);
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(pickup.lat)) * Math.cos(toRad(destination.lat)) * Math.sin(dLng / 2) ** 2;
  const distanceKm = EARTH_RADIUS_KM * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  const rawFare = Math.max(BASE_FARE, BASE_FARE + distanceKm * RATE_PER_KM);
  return {
    distanceKm: Number(distanceKm.toFixed(2)),
    fareAmount: Math.round(rawFare * 100) / 100,
  };
}

export const formatVnd = amount =>
  new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
