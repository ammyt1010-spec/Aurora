import { apiRequest } from './client.js';

export const getBillingPolicy = () => apiRequest('/billing/policy');
export const isOperator = () => apiRequest('/billing/operator-status');
export const getTariffs = () => apiRequest('/billing/tariffs');
export const createTariff = (data) => apiRequest('/billing/tariffs', { method: 'POST', body: data });
export const editTariff = (id, data) => apiRequest(`/billing/tariffs/${id}`, { method: 'PUT', body: data });
export const getOrders = (studyId) => apiRequest(`/billing/studies/${studyId}/orders`);
export const requestQuote = (studyId, workers, methodCode) => apiRequest(`/billing/studies/${studyId}/quotes`, {
  method: 'POST', body: { workers: Number(workers), method_code: methodCode },
});
export const getPendingOrders = () => apiRequest('/billing/pending-orders');
export const approvePayment = (id, paymentReference) => apiRequest(`/billing/orders/${id}/confirm-payment`, {
  method: 'POST', body: { payment_reference: paymentReference },
});


export const loadReferenceTariffs = () =>
  apiRequest('/billing/tariffs/load-reference', { method: 'POST' });

export const priceManualQuote = (id, amount) =>
  apiRequest(`/billing/orders/${id}/set-manual-price`, {
    method: 'POST', body: { amount },
  });

export const BILLING_METHODS = [
  { code: 'SUSESO_ISTAS21_BREVE', label: 'SUSESO / ISTAS21 breve' },
  { code: 'CENSOPAS_CORTA', label: 'CENSOPAS COPSOQ corta' },
  { code: 'CENSOPAS_MEDIA', label: 'CENSOPAS COPSOQ media' },
];
