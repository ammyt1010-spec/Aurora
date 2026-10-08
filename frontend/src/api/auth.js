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
