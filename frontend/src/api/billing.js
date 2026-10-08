import { apiRequest } from './client.js';

export const getBillingPolicy = () => apiRequest('/billing/policy');
export const isOperator = () => apiRequest('/billing/operator-status');
export const getTariffs = () => apiRequest('/billing/tariffs');
export const createTariff = (data) => apiRequest('/billing/tariffs', { method: 'POST', body: data });
export const editTariff = (id, data) => apiRequest(`/billing/tariffs/${id}`, { method: 'PUT', body: data });
export const getOrders = (studyId) => apiRequest(`/billing/studies/${studyId}/orders`);
export const requestQuote = (studyId, workers) => apiRequest(`/billing/studies/${studyId}/quotes`, {
  method: 'POST', body: { workers: Number(workers) },
});
export const getPendingOrders = () => apiRequest('/billing/pending-orders');
export const approvePayment = (id, paymentReference) => apiRequest(`/billing/orders/${id}/confirm-payment`, {
  method: 'POST', body: { payment_reference: paymentReference },
});
