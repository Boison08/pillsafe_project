export const MOCK_USER = {
  id: 1,
  fullName: 'Maxwell Donkor',
  caregiverPhone: '+233 24 000 0001',
  compartmentIndex: 0,
  enrolled: true,
};

export const MOCK_SCHEDULES = [
  { id: 1, medicationName: 'Lisinopril 10mg', dosage: '1 tablet', dispenseTimes: ['07:00'], repeatDays: [1,1,1,1,1,1,1], gracePeriodMinutes: 15 },
  { id: 2, medicationName: 'Atorvastatin 20mg', dosage: '1 tablet', dispenseTimes: ['08:00'], repeatDays: [1,1,1,1,1,1,1], gracePeriodMinutes: 15 },
  { id: 3, medicationName: 'Metformin 500mg', dosage: '1 tablet', dispenseTimes: ['13:00','23:00'], repeatDays: [1,1,1,1,1,1,1], gracePeriodMinutes: 15 },
  { id: 4, medicationName: 'Aspirin 81mg', dosage: '1 tablet', dispenseTimes: ['20:00'], repeatDays: [1,1,1,1,1,1,1], gracePeriodMinutes: 15 },
];

export const MOCK_ADHERENCE = [
  { medicationName: 'Lisinopril 10mg', scheduledAt: new Date(Date.now() - 3600000 * 3).toISOString(), status: 'taken' },
  { medicationName: 'Metformin 500mg', scheduledAt: new Date(Date.now() - 3600000 * 13).toISOString(), status: 'missed' },
  { medicationName: 'Aspirin 81mg', scheduledAt: new Date(Date.now() - 3600000 * 30).toISOString(), status: 'taken' },
  { medicationName: 'Lisinopril 10mg', scheduledAt: new Date(Date.now() - 3600000 * 27).toISOString(), status: 'taken' },
  { medicationName: 'Atorvastatin 20mg', scheduledAt: new Date(Date.now() - 3600000 * 26).toISOString(), status: 'taken' },
];

export const MOCK_NOTIFICATIONS = [
  { id: 1, type: 'dispensed', title: 'Dose dispensed', detail: 'Lisinopril 10mg · Slot A — Pickup confirmed by IR sensor', timestamp: new Date(Date.now() - 3600000 * 3).toISOString(), read: false },
  { id: 2, type: 'missed', title: 'Missed dose', detail: 'Metformin 500mg · Slot C — Grace period expired. SMS sent.', timestamp: new Date(Date.now() - 3600000 * 13).toISOString(), read: false },
  { id: 3, type: 'failedVerification', title: 'Verification failed', detail: '3 attempts exceeded. Dispense blocked. Caregiver notified.', timestamp: new Date(Date.now() - 3600000 * 14).toISOString(), read: true },
  { id: 4, type: 'dispensed', title: 'Dose dispensed', detail: 'Aspirin 81mg · Slot D — Pickup confirmed', timestamp: new Date(Date.now() - 3600000 * 30).toISOString(), read: true },
  { id: 5, type: 'deviceAlert', title: 'Device reconnected', detail: 'PillSafe hotspot re-established after 4 min offline', timestamp: new Date(Date.now() - 3600000 * 32).toISOString(), read: true },
];

export const MOCK_DEVICE = {
  connected: true,
  rtcTime: '09:41:02',
  gsmSignal: 'Strong',
  slotsLoaded: 4,
  faceModel: 'MobileFaceNet TFLite',
  lastDispense: '07:00 · Slot A',
};

export const MED_COLORS = ['#1D6FE8', '#0EA472', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4'];

export const slotLabel = (index) => String.fromCharCode(65 + index);
export const greeting = () => {
  const hour = new Date().getHours();
  return hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
};
export const fmtRelTime = (iso) => {
  const diffDays = Math.floor((Date.now() - new Date(iso)) / 86400000);
  const time = new Date(iso).toLocaleTimeString('en', { hour: 'numeric', minute: '2-digit' });
  return diffDays === 0 ? `Today, ${time}` : diffDays === 1 ? `Yesterday, ${time}` : `${new Date(iso).toLocaleDateString('en', { weekday: 'short', day: 'numeric', month: 'short' })}, ${time}`;
};
