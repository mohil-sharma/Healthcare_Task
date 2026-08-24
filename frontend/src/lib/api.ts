/**
 * Typed API client for the Healthcare backend.
 * All functions route through Vite's /api proxy during development.
 */

const API_BASE = '/api';

function getAuthHeaders() {
    const token = localStorage.getItem('token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

export interface HealthResponse {
  status: string;
  db: string;
  latency_ms: number;
}

export async function fetchHealth(): Promise<HealthResponse> {
    const response = await fetch(`${API_BASE}/health`);
    if (!response.ok) {
        throw new Error('Network response was not ok');
    }
    return response.json();
}

export async function login(username, password) {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    
    const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData
    });
    
    if (!response.ok) {
        throw new Error('Login failed');
    }
    
    const data = await response.json();
    localStorage.setItem('token', data.access_token);
    return data;
}

export async function getAdminDoctors() {
    const response = await fetch(`${API_BASE}/admin/doctors`, {
        headers: getAuthHeaders()
    });
    if (!response.ok) throw new Error('Failed to fetch doctors');
    return response.json();
}

export async function updateDoctorAdmin(id, data) {
    const response = await fetch(`${API_BASE}/admin/doctors/${id}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            ...getAuthHeaders()
        },
        body: JSON.stringify(data)
    });
    if (!response.ok) throw new Error('Failed to update doctor');
    return response.json();
}

export async function createDoctorAdmin(data) {
    const response = await fetch(`${API_BASE}/admin/doctors`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...getAuthHeaders()
        },
        body: JSON.stringify(data)
    });
    if (!response.ok) throw new Error('Failed to create doctor');
    return response.json();
}

export async function addDoctorLeaveAdmin(id, leaveDate, reason) {
    const response = await fetch(`${API_BASE}/admin/doctors/${id}/leave`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...getAuthHeaders()
        },
        body: JSON.stringify({ leave_date: leaveDate, reason: reason || null })
    });
    if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to add leave day');
    }
    return response.json();
}
