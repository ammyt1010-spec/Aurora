import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CreditCard, CheckCircle2, Clock, FileText, Building2, ShieldCheck } from 'lucide-react';

import { listOrganizations } from '../../api/organizations.js';
import { getOrganizationBillingSummary, BILLING_METHODS } from '../../api/billing.js';
import { Card } from '../ui/Card.jsx';

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('es-PE', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date);
}

const STATUS_BADGES = {
  PAID: { label: 'Disponible', className: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  CONSUMED: { label: 'Consumida', className: 'bg-blue-50 text-blue-700 border-blue-200' },
  PENDING_PAYMENT: { label: 'Pendiente de pago', className: 'bg-amber-50 text-amber-800 border-amber-200' },
  AWAITING_QUOTE: { label: 'Por cotizar', className: 'bg-purple-50 text-purple-700 border-purple-200' },
  RESERVED: { label: 'En proceso', className: 'bg-yellow-50 text-yellow-800 border-yellow-200' },
};

export function EnterpriseBillingPanel() {
  const [selectedOrganizationId, setSelectedOrganizationId] = useState(null);

  const { data: memberships = [], isPending: loadingOrganizations } = useQuery({
    queryKey: ['enterprise-billing-organizations'],
    queryFn: listOrganizations,
    retry: false,
  });

  const managedOrganizations = memberships.filter(
    (entry) => ['OWNER', 'ADMIN'].includes(entry.role_code),
  );

  const activeOrganizationId = managedOrganizations.some(
    (entry) => entry.organization.id === selectedOrganizationId,
  )
    ? selectedOrganizationId
    : managedOrganizations[0]?.organization.id;

  const { data: summary, isPending: loadingSummary, isError } = useQuery({
    queryKey: ['enterprise-billing-summary', activeOrganizationId],
    queryFn: () => getOrganizationBillingSummary(activeOrganizationId),
    enabled: activeOrganizationId != null,
    retry: false,
  });

  if (loadingOrganizations) {
    return (
      <Card className="p-5">
        <p className="text-xs text-muted">Cargando estado comercial de la empresa...</p>
      </Card>
    );
  }

  if (!managedOrganizations.length) {
    return null;
  }

  const orders = summary?.orders || [];

  return (
    <Card className="p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
        <div>
          <h2 className="flex items-center gap-2 text-base font-bold text-dark">
            <CreditCard size={18} className="text-primary" /> Integridad y Licencias Comerciales
          </h2>
          <p className="text-xs text-muted">
            Control de cotizaciones, tarifas congeladas y licencias de emisión de informes por empresa.
          </p>
        </div>

        {managedOrganizations.length > 1 && (
          <div className="flex items-center gap-2">
            <Building2 size={16} className="text-muted" />
            <select
              aria-label="Seleccionar empresa para consultar licencias"
              className="colmena-input text-xs"
              value={activeOrganizationId || ''}
              onChange={(e) => setSelectedOrganizationId(Number(e.target.value))}
            >
              {managedOrganizations.map((entry) => (
                <option key={entry.organization.id} value={entry.organization.id}>
                  {entry.organization.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {loadingSummary ? (
        <p className="text-xs text-muted py-2">Consultando balance de licencias...</p>
      ) : isError ? (
        <p role="alert" className="text-xs text-red-700 py-2">
          No se pudo consultar el estado comercial de la empresa seleccionada.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-3 text-center">
              <span className="flex items-center justify-center gap-1 text-xs font-semibold text-emerald-800">
                <CheckCircle2 size={14} /> Disponibles
              </span>
              <p className="mt-1 text-2xl font-black text-emerald-700">
                {summary?.available_licenses ?? 0}
              </p>
              <span className="text-[10px] text-muted">Órdenes listas</span>
            </div>

            <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-3 text-center">
              <span className="flex items-center justify-center gap-1 text-xs font-semibold text-blue-800">
                <FileText size={14} /> Emitidos
              </span>
              <p className="mt-1 text-2xl font-black text-blue-700">
                {summary?.consumed_licenses ?? 0}
              </p>
              <span className="text-[10px] text-muted">Informes generados</span>
            </div>

            <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-3 text-center">
              <span className="flex items-center justify-center gap-1 text-xs font-semibold text-amber-800">
                <Clock size={14} /> Por Pagar
              </span>
              <p className="mt-1 text-2xl font-black text-amber-700">
                {summary?.pending_payment ?? 0}
              </p>
              <span className="text-[10px] text-muted">Cotizaciones activas</span>
            </div>

            <div className="rounded-lg border border-border bg-slate-50/60 p-3 text-center">
              <span className="flex items-center justify-center gap-1 text-xs font-semibold text-dark">
                <ShieldCheck size={14} /> Total
              </span>
              <p className="mt-1 text-2xl font-black text-dark">
                {summary?.total_orders ?? 0}
              </p>
              <span className="text-[10px] text-muted">Historial completo</span>
            </div>
          </div>

          <div className="space-y-2 pt-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-muted">
              Historial de Órdenes y Cotizaciones
            </h3>

            {orders.length === 0 ? (
              <p className="text-xs text-muted py-3">
                No hay órdenes registradas para esta empresa. Las cotizaciones se solicitan desde cada estudio.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border border-border divide-y divide-border rounded-lg">
                  <thead className="bg-slate-50 text-[11px] font-semibold text-dark">
                    <tr>
                      <th className="px-3 py-2">Orden</th>
                      <th className="px-3 py-2">Metodología</th>
                      <th className="px-3 py-2">Dotación</th>
                      <th className="px-3 py-2">Importe</th>
                      <th className="px-3 py-2">Estado</th>
                      <th className="px-3 py-2">Referencia</th>
                      <th className="px-3 py-2">Fecha</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {orders.map((order) => {
                      const method = BILLING_METHODS.find((m) => m.code === order.method_code);
                      const badge = STATUS_BADGES[order.status] || {
                        label: order.status,
                        className: 'bg-slate-100 text-slate-700 border-slate-200',
                      };
                      return (
                        <tr key={order.id} className="hover:bg-slate-50/60">
                          <td className="px-3 py-2 font-mono font-bold text-dark">
                            #{order.id}
                          </td>
                          <td className="px-3 py-2 font-medium text-dark">
                            {method?.label || order.method_code}
                          </td>
                          <td className="px-3 py-2 text-muted">
                            <span className="font-semibold text-dark">{order.workers}</span> trab.
                            {order.headcount_source && (
                              <span className="ml-1 text-[10px] text-muted block">
                                {order.headcount_source}
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2 font-semibold text-dark">
                            {order.amount ? `S/ ${order.amount}` : 'Cotizar'}
                          </td>
                          <td className="px-3 py-2">
                            <span
                              className={`inline-block rounded border px-2 py-0.5 text-[10px] font-semibold ${badge.className}`}
                            >
                              {badge.label}
                            </span>
                          </td>
                          <td className="px-3 py-2 font-mono text-[11px] text-muted">
                            {order.payment_reference || '—'}
                          </td>
                          <td className="px-3 py-2 text-muted">
                            {formatDate(order.paid_at || order.created_at)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </Card>
  );
}
