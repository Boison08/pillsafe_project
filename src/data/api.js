// Use localhost for development, or 192.168.4.1 for Pi device
const BASE_URL = 'http://localhost:5000';

const fetchJson = async (path, options = {}) => {
  const response = await fetch(`${BASE_URL}${path}`, options);
  if (!response.ok) throw new Error(response.status);
  return response.json();
};

export const api = {
  getUsers: () => fetchJson('/users'),
  createUser: (user) => fetchJson('/users', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(user) }),
  getSlots: () => fetchJson('/slots'),
  startEnrolment: (userId) => fetchJson('/enrol/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: userId }) }),
  getEnrolmentProgress: (userId) => fetchJson(`/enrol/progress?user_id=${userId}`),
  finaliseEnrolment: (userId) => fetchJson('/enrol/finalise', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: userId }) }),
  verifyFace: (userId) => fetchJson('/verify', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: userId }) }),
  getSchedules: (userId) => fetchJson(`/schedules?user_id=${userId}`),
  createSchedule: (schedule) => fetchJson('/schedules', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(schedule) }),
  deleteSchedule: (id) => fetchJson(`/schedules/${id}`, { method: 'DELETE' }),
  getAdherence: (userId, days = 7) => fetchJson(`/adherence?user_id=${userId}&days=${days}`),
  getNotifications: (userId) => fetchJson(`/notifications?user_id=${userId}`),
  markRead: (userId) => fetchJson(`/notifications/read?user_id=${userId}`, { method: 'PATCH' }),
  getDeviceStatus: () => fetchJson('/device/status'),
};
