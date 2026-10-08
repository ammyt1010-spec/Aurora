import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ShieldCheck, CreditCard, Settings2 } from 'lucide-react';
import { PageHeader } from '../../components/layout/PageHeader.jsx';
import { Card } from '../../components/ui/Card.jsx';
import { getTariffs, createTariff, editTariff, getPendingOrders, approvePayment, isOperator } from '../../api/billing.js';
import { useAuth } from '../../auth/AuthContext.jsx';

export default function SettingsPage() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const [minWorkers, setMinWorkers] = useState('1');
  const [maxWorkers, setMaxWorkers] = useState('');
  const [price, setPrice] = useState('');
  const [paymentRefs, setPaymentRefs] = useState({});
  const [notice, setNotice] = useState('');
  const { data: operatorStatus } = useQuery({ queryKey: ['aurora-operator'], queryFn: isOperator });
  const enabled = operatorStatus?.is_operator === true;
  const { data: tariffs = [] } = useQuery({ queryKey: ['aurora-tariffs'], queryFn: getTariffs, enabled });
  const { data: orders = [] } = useQuery({ queryKey: ['aurora-unpaid'], queryFn: getPendingOrders, enabled });
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['aurora-tariffs'] });
    qc.invalidateQueries({ queryKey: ['aurora-unpaid'] });
  };
  const add = useMutation({
    mutationFn: () => createTariff({
      min_workers: Number(minWorkers), max_workers: maxWorkers ? Number(maxWorkers) : null,
      price, currency: 'PEN', active: true,
    }),
    onSuccess: () => { invalidate(); setPrice(''); setNotice('Nuevo tramo guardado.'); },
    onError: (error) => setNotice(error.message),
  });
  const change = useMutation({
    mutationFn: ({ id, row }) => editTariff(id, row),
    onSuccess: () => { invalidate(); setNotice('Tarifario actualizado.'); },
    onError: (error) => setNotice(error.message),
  });
  const verify = useMutation({
    mutationFn: (id) => approvePayment(id, paymentRefs[id] || ''),
    onSuccess: () => { invalidate(); setNotice('Pago registrado por el operador.'); },
    onError: (error) => setNotice(error.message),
  });

  return (
    <div className="colmena-page space-y-5">
      <PageHeader title="Administración de AURORA"
        description="Plataforma empresarial privada · Pago por informe según cantidad de trabajadores." />
      <Card className="p-5 space-y-2">
        <h2 className="flex items-center gap-2 text-base font-bold text-dark"><Settings2 size={18} /> Mi cuenta</h2>
        <p className="text-sm text-muted">Usuario: {user?.username || '—'} · {user?.email || '—'}</p>
        <p className="text-xs text-muted">Los permisos empresariales se gestionan dentro de cada proyecto.</p>
      </Card>
      {enabled ? (
        <>
          <Card className="p-5 space-y-3">
            <h2 className="flex items-center gap-2 font-bold text-dark"><CreditCard size={18}/> Tarifario editable (PEN)</h2>
            <p className="text-xs text-muted">El importe corresponde a una solicitud de informe, no al pago por cada trabajador. Editar una tarifa no modifica cotizaciones emitidas.</p>
            <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); add.mutate(); }}>
              <label className="text-xs font-semibold text-dark">Desde
                <input className="colmena-input mt-1 block w-28" type="number" min="1" required value={minWorkers}
                  onChange={(e) => setMinWorkers(e.target.value)} />
              </label>
              <label className="text-xs font-semibold text-dark">Hasta (vacío = sin límite)
                <input className="colmena-input mt-1 block w-36" type="number" min="1" value={maxWorkers}
                  onChange={(e) => setMaxWorkers(e.target.value)} />
              </label>
              <label className="text-xs font-semibold text-dark">Tarifa S/
                <input className="colmena-input mt-1 block w-32" type="number" min="0.01" step="0.01" required value={price}
                  onChange={(e) => setPrice(e.target.value)} />
              </label>
              <button disabled={add.isPending} className="rounded-lg bg-amber px-4 py-2 font-bold text-xs text-dark">Agregar tramo</button>
            </form>
            <div className="divide-y divide-border">
              {tariffs.map(t => (
                <div key={t.id} className="flex flex-wrap items-center justify-between gap-3 py-2 text-xs">
                  <span className="font-semibold text-dark">{t.min_workers} – {t.max_workers ?? '∞'} trabajadores · S/ {t.price}</span>
                  <div className="flex gap-2">
                    <button type="button" className="rounded border border-border px-3 py-1"
                      onClick={() => {
                        const entered = window.prompt('Nuevo precio en soles para este tramo:', String(t.price));
                        if (entered === null) return;
                        if (!/^\d+(\.\d{1,2})?$/.test(entered) || Number(entered) <= 0) { setNotice('Precio inválido.'); return; }
                        change.mutate({ id: t.id, row: { min_workers: t.min_workers, max_workers: t.max_workers, price: entered, currency: 'PEN', active: true } });
                      }}>Cambiar precio</button>
                    <button type="button" className="rounded border border-border px-3 py-1"
                      onClick={() => {
                        if (window.confirm('¿Desactivar este tramo para nuevas cotizaciones?')) change.mutate({ id: t.id, row: { min_workers: t.min_workers, max_workers: t.max_workers, price: t.price, currency: 'PEN', active: false } });
                      }}>Desactivar</button>
                  </div>
                </div>
              ))}
              {!tariffs.length && <p className="text-xs py-3 text-muted">No hay tarifas. Introduce los importes cuando estén definidos.</p>}
            </div>
          </Card>
          <Card className="p-5 space-y-3">
            <h2 className="font-bold text-dark flex items-center gap-2"><ShieldCheck size={18}/> Pagos pendientes de verificar</h2>
            <p className="text-xs text-muted">Verifica el depósito o comprobante por un canal seguro antes de aprobar. Introducir una referencia no verifica automáticamente el pago bancario.</p>
            {orders.map(order => (
              <div key={order.id} className="flex flex-wrap gap-3 justify-between border-b border-border py-2">
                <div className="text-xs">
                  <p className="font-bold text-dark">Orden #{order.id} · Empresa #{order.organization_id}</p>
                  <p className="text-muted">{order.workers} trabajadores · S/ {order.amount} · Estudio #{order.study_id}</p>
                </div>
                <form className="flex flex-wrap gap-2" onSubmit={(event) => { event.preventDefault(); verify.mutate(order.id); }}>
                  <input aria-label={`Referencia de pago para orden ${order.id}`} className="colmena-input" required minLength={4}
                    placeholder="Referencia verificada" value={paymentRefs[order.id] || ''}
                    onChange={(e) => setPaymentRefs(v => ({ ...v, [order.id]: e.target.value }))} />
                  <button disabled={verify.isPending} className="rounded-lg bg-amber px-3 py-2 text-xs font-bold text-dark">Confirmar pago</button>
                </form>
              </div>
            ))}
            {!orders.length && <p className="text-xs text-muted">Sin pagos pendientes de revisión.</p>}
          </Card>
          {notice && <p role="status" className="text-xs text-muted">{notice}</p>}
        </>
      ) : (
        <Card className="p-5">
          <p className="text-sm text-muted">El tarifario y la confirmación de pagos solo aparecen en la cuenta administradora central de AURORA.</p>
        </Card>
      )}
    </div>
  );
}
