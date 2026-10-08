import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { CreditCard, Users } from 'lucide-react';

import { BILLING_METHODS, getOrders, requestQuote } from '../../../api/billing.js';
import { Card } from '../../ui/Card.jsx';

const currency = (value, code = 'PEN') => new Intl.NumberFormat('es-PE', {
  style: 'currency', currency: code,
}).format(Number(value));

function guessMethod(study) {
  const name = (study?.instrument_name || '').toUpperCase();
  const version = (study?.instrument_version_code || '').toUpperCase();
  if (name.includes('CENSOPAS') || name.includes('COPSOQ')) {
    return ['MEDIUM', 'MEDIA'].includes(version) ? 'CENSOPAS_MEDIA' : 'CENSOPAS_CORTA';
  }
  return 'SUSESO_ISTAS21_BREVE';
}

export default function ReportBillingPanel({ studyId, study, selectedOrderId, onSelectOrder }) {
  const qc = useQueryClient();
  const [workers, setWorkers] = useState('');
  const [methodCode, setMethodCode] = useState(() => guessMethod(study));
  useEffect(() => setMethodCode(guessMethod(study)), [studyId, study?.instrument_name, study?.instrument_version_code]);
  const { data: orders = [] } = useQuery({
    queryKey: ['report-orders', studyId], queryFn: () => getOrders(studyId), enabled: Boolean(studyId),
  });
  const quote = useMutation({
    mutationFn: () => requestQuote(studyId, workers, methodCode),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['report-orders', studyId] }); setWorkers(''); },
  });
  const ready = orders.filter((order) => order.status === 'PAID');
  return (
    <Card className="p-4 space-y-4">
      <div className="flex items-center gap-2">
        <CreditCard size={17} className="text-amber" />
        <h3 className="text-sm font-bold text-dark">Pago por informe</h3>
      </div>
      <p className="text-xs text-muted">Cada informe requiere una cotización según los trabajadores de la empresa. No se cobra una suscripción.</p>
      <form onSubmit={(event) => { event.preventDefault(); quote.mutate(); }} className="space-y-2">
        <label className="text-xs font-semibold text-dark" htmlFor="billing-method">Metodología de evaluación</label>
        <select id="billing-method" className="colmena-input w-full" value={methodCode} onChange={(e) => setMethodCode(e.target.value)}>
          {BILLING_METHODS.map((method) => <option key={method.code} value={method.code}>{method.label}</option>)}
        </select>
        <label htmlFor="billing-workers" className="text-xs font-semibold text-dark">Número de trabajadores</label>
        <div className="flex gap-2">
          <input id="billing-workers" aria-label="Número de trabajadores" type="number" min="1" max="10000000"
            required className="colmena-input min-w-0 w-full" value={workers}
            onChange={(event) => setWorkers(event.target.value)} placeholder="Ej. 85" />
          <button type="submit" disabled={quote.isPending || !Number.isInteger(Number(workers)) || Number(workers) < 1}
            className="rounded-xl bg-amber px-3 py-2 text-xs font-bold text-dark disabled:opacity-50">
            {quote.isPending ? 'Cotizando…' : 'Solicitar cotización'}
          </button>
        </div>
        {quote.isError && <p role="alert" className="text-xs text-danger">{quote.error.message}</p>}
      </form>
      <div className="space-y-2">
        {orders.map((order) => (
          <div key={order.id} className="flex flex-wrap justify-between items-center gap-2 rounded-lg bg-surfaceSoft border border-border p-2">
            <div className="text-xs">
              <p className="font-bold text-dark">Orden #{order.id} · {order.amount == null ? 'Cotizar' : currency(order.amount, order.currency)}</p>
              <p className="text-muted">{BILLING_METHODS.find((method) => method.code === order.method_code)?.label || order.method_code}</p>
              <p className="text-muted flex items-center gap-1"><Users size={12} /> {order.workers} trabajadores · {
                order.status === 'PAID' ? 'Pago confirmado' : order.status === 'CONSUMED' ? 'Informe emitido' : order.status === 'AWAITING_QUOTE' ? 'Pendiente de precio personalizado' : 'Pendiente de confirmación'
              }</p>
            </div>
            {order.status === 'PAID' && (
              <button type="button" onClick={() => onSelectOrder(order.id)}
                className={`rounded-lg border px-2 py-1 text-xs font-semibold ${Number(selectedOrderId) === order.id ? 'border-amber bg-amber/20' : 'border-border'}`}>
                {Number(selectedOrderId) === order.id ? 'Seleccionada' : 'Utilizar orden'}
              </button>
            )}
          </div>
        ))}
        {!orders.length && <p className="text-xs text-muted">Todavía no existen cotizaciones para este estudio.</p>}
      </div>
      {ready.length === 0 && <p className="text-xs text-muted">Cuando el administrador central verifique el pago, la orden aparecerá aquí como disponible.</p>}
    </Card>
  );
}
