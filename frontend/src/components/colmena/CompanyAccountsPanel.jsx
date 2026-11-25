import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { KeyRound, Search, Users } from 'lucide-react';

import { listCompanyAccounts, resetCompanyAccountPassword, setCompanyAccountStatus } from '../../api/auth.js';
import { Card } from '../ui/Card.jsx';

function newPassword() {
  const bytes = window.crypto.getRandomValues(new Uint8Array(24));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
}

export function CompanyAccountsPanel() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const [issued, setIssued] = useState(null);
  const [notice, setNotice] = useState('');
  const { data, isPending, isError } = useQuery({
    queryKey: ['company-accounts', query, offset],
    queryFn: () => listCompanyAccounts({ q: query, offset }),
  });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['company-accounts'] });
  const changeStatus = useMutation({
    mutationFn: ({ id, status }) => setCompanyAccountStatus(id, status),
    onSuccess: () => { invalidate(); setNotice('Estado actualizado. Las sesiones anteriores quedaron invalidadas.'); },
    onError: (error) => setNotice(error.message),
  });
  const resetPassword = useMutation({
    mutationFn: ({ id, password }) => resetCompanyAccountPassword(id, password),
    onSuccess: (_result, { email, password }) => {
      setIssued({ email, password });
      setNotice('Clave restablecida. Compártela únicamente por un canal privado.');
    },
    onError: (error) => setNotice(error.message),
  });

  return (
    <Card className="space-y-3 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-base font-bold text-dark"><Users size={18} /> Cuentas empresariales</h2>
          <p className="text-sm text-muted">Busca, revisa cupos, suspende accesos y restablece claves.</p>
        </div>
        <span className="text-sm font-semibold text-[#315788]">{data?.total ?? '—'} cuentas</span>
      </div>
      <form className="flex gap-2" onSubmit={(event) => {
        event.preventDefault(); setOffset(0); setQuery(search.trim());
      }}>
        <input className="colmena-input min-w-0 flex-1" aria-label="Buscar cuentas" placeholder="Empresa, RUC o correo" value={search} onChange={(event) => setSearch(event.target.value)} />
        <button type="submit" className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-semibold"><Search size={16} /> Buscar</button>
      </form>
      {isPending && <p className="text-sm text-muted">Cargando cuentas…</p>}
      {isError && <p role="alert" className="text-sm text-red-700">No se pudieron cargar las cuentas.</p>}
      <div className="divide-y divide-border">
        {data?.items?.map((account) => (
          <article key={account.user_id} className="flex flex-wrap items-center justify-between gap-3 py-3">
            <div className="min-w-0">
              <p className="text-sm font-bold text-dark">{account.company_name} <span className="font-normal text-muted">· RUC {account.company_ruc}</span></p>
              <p className="break-all text-sm text-muted">{account.email} · {account.company_workers ?? '—'} trabajadores · {account.free_remaining} de 4 evaluaciones gratis restantes</p>
              <span className={`text-xs font-bold ${account.status === 'ACTIVE' ? 'text-emerald-700' : 'text-red-700'}`}>{account.status === 'ACTIVE' ? 'Activa' : 'Suspendida'}</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <button type="button" disabled={changeStatus.isPending} className="rounded-lg border border-border px-3 py-2 text-sm font-semibold"
                onClick={() => {
                  const status = account.status === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE';
                  if (status === 'SUSPENDED' && !window.confirm(`¿Suspender el acceso de ${account.company_name}?`)) return;
                  changeStatus.mutate({ id: account.user_id, status });
                }}>
                {account.status === 'ACTIVE' ? 'Suspender acceso' : 'Reactivar'}
              </button>
              <button type="button" disabled={resetPassword.isPending} className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-2 text-sm font-semibold"
                onClick={() => {
                  if (!window.confirm(`¿Restablecer la clave de ${account.email}? Se cerrarán sus sesiones.`)) return;
                  resetPassword.mutate({ id: account.user_id, email: account.email, password: newPassword() });
                }}><KeyRound size={15} /> Nueva clave</button>
            </div>
          </article>
        ))}
        {data && data.items.length === 0 && <p className="py-4 text-sm text-muted">No hay cuentas que coincidan con la búsqueda.</p>}
      </div>
      {data && data.total > 50 && <div className="flex items-center justify-end gap-2 text-sm">
        <button type="button" className="rounded-lg border border-border px-3 py-1" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Anterior</button>
        <span>{offset + 1}–{Math.min(offset + 50, data.total)} de {data.total}</span>
        <button type="button" className="rounded-lg border border-border px-3 py-1" disabled={offset + 50 >= data.total} onClick={() => setOffset(offset + 50)}>Siguiente</button>
      </div>}
      {notice && <p role="status" className="text-sm text-[#315788]">{notice}</p>}
      {issued && <div role="status" className="rounded-lg bg-[#EDF9FB] p-3 text-sm text-dark">
        <strong>{issued.email}</strong> · Nueva clave: <code className="break-all font-semibold">{issued.password}</code>
        <button type="button" className="ml-3 font-bold text-[#176486] underline" onClick={() => setIssued(null)}>Ocultar</button>
      </div>}
    </Card>
  );
}
