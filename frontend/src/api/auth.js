import { apiRequest } from './client.js';

export function registerUser({ email, username, password, firstName, lastName }) {
  return apiRequest('/auth/register', {
    method: 'POST',
    skipAuth: true,
    body: {
      email,
      username,
      password,
      first_name: firstName || null,
      last_name: lastName || null,
    },
  });
}

export function createCompanyAccount(payload) {
  return apiRequest('/auth/company-accounts', { method: 'POST', body: payload });
}

export function signupCompanyAccount(payload) {
  return apiRequest('/auth/company-signup', { method: 'POST', body: payload, skipAuth: true });
}

export function verifyCompanyEmail(token) {
  return apiRequest('/auth/verify-company-email', { method: 'POST', body: { token }, skipAuth: true });
}

export function resendCompanyVerification(email) {
  return apiRequest('/auth/resend-company-verification', { method: 'POST', body: { email }, skipAuth: true });
}

export function listCompanyAccounts({ q = '', limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ q, limit: String(limit), offset: String(offset) });
  return apiRequest(`/auth/company-accounts?${params}`);
}

export function setCompanyAccountStatus(userId, status) {
  return apiRequest(`/auth/company-accounts/${userId}/status`, { method: 'PATCH', body: { status } });
}

export function resetCompanyAccountPassword(userId, newPassword) {
  return apiRequest(`/auth/company-accounts/${userId}/reset-password`, {
    method: 'POST', body: { new_password: newPassword },
  });
}

export function getRegistrationPolicy() {
  return apiRequest('/auth/registration-policy', { skipAuth: true });
}

export function loginUser({ email, password }) {
  return apiRequest('/auth/login', {
    method: 'POST',
    skipAuth: true,
    body: { email, password },
  });
}

export function demoLoginUser() {
  return apiRequest('/auth/demo-login', {
    method: 'POST',
    skipAuth: true,
  });
}

export function fetchCurrentUser() {
  return apiRequest('/auth/me');
}

export function logoutUser() {
  return apiRequest('/auth/logout', { method: 'POST' });
}

export function logoutAllUser() {
  return apiRequest('/auth/logout-all', { method: 'POST' });
}
