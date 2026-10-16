import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Laptop, Smartphone, Tablet, Monitor, Shield, RefreshCw } from 'lucide-react';

import { listUserSessions, revokeUserSession, revokeOtherUserSessions } from '../../api/sessions.js';
import { Card } from '../ui/Card.jsx';

function formatSessionDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('es-PE', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date);
}

function getDeviceIcon(deviceFamily) {
  const family = (deviceFamily || '').toLowerCase();
  if (family === 'mobile') return <Smartphone size={18} className="text-muted" />;
  if (family === 'tablet') return <Tablet size={18} className="text-muted" />;
  if (family === 'desktop') return <Laptop size={18} className="text-muted" />;
  return <Monitor size={18} className="text-muted" />;
}

export function SessionManagementPanel() {
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  const {
    data: sessions = [],
    isPending,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['user-active-sessions'],
    queryFn: listUserSessions,
    retry: false,
  });

  const revokeMutation = useMutation({
    mutationFn: (sessionId) => revokeUserSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-active-sessions'] });
      setNotice('Sesión remota revocada exitosamente.');
      setErrorMessage('');
    },
    onError: () => {
      setErrorMessage('No se pudo revocar la sesión remota.');
    },
  });

  const revokeOthersMutation = useMutation({
    mutationFn: () => revokeOtherUserSessions(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['user-active-sessions'] });
      setNotice(data?.message || 'Se cerraron las demás sesiones activas.');
      setErrorMessage('');
    },
    onError: () => {
      setErrorMessage('No se pudieron cerrar las demás sesiones.');
    },
  });

  const otherSessionsCount = sessions.filter((s) => !s.is_current).length;

  const handleRevokeSingle = (sessionId) => {
    if (!window.confirm('¿Deseas cerrar la sesión en este dispositivo?')) return;
    setNotice('');
    revokeMutation.mutate(sessionId);
  };

  const handleRevokeOthers = () => {
    if (!window.confirm('¿Cerrar todas las demás sesiones activas en otros dispositivos?')) return;
    setNotice('');
    revokeOthersMutation.mutate();
  };

  return (
    <Card className="space-y-4 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-base font-bold text-dark">
            <Shield size={18} /> Dispositivos y sesiones activas
          </h2>
          <p className="mt-1 text-xs text-muted">
            Gestiona los dispositivos y navegadores autorizados en tu cuenta. No se almacenan contraseñas ni ubicaciones exactas.
          </p>
        </div>
        <div className="flex gap-2">
          {otherSessionsCount > 0 && (
            <button
              type="button"
              disabled={revokeOthersMutation.isPending}
              onClick={handleRevokeOthers}
              className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50"
            >
              {revokeOthersMutation.isPending ? 'Cerrando sesiones…' : 'Cerrar las demás sesiones'}
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              setNotice('');
              refetch();
            }}
            disabled={isPending}
            className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-dark disabled:opacity-50"
          >
            <RefreshCw size={14} /> Actualizar
          </button>
        </div>
      </div>

      {notice && <p role="status" className="text-xs font-medium text-emerald-700">{notice}</p>}
      {errorMessage && <p role="alert" className="text-xs font-medium text-red-700">{errorMessage}</p>}
      {isPending && <p className="text-xs text-muted">Consultando sesiones activas…</p>}
      {isError && <p role="alert" className="text-xs text-red-700">No se pudieron consultar tus sesiones activas.</p>}

      {!isPending && !isError && sessions.length === 0 && (
        <p className="text-xs text-muted">No hay sesiones activas registradas.</p>
      )}

      {sessions.length > 0 && (
        <div className="divide-y divide-border rounded-lg border border-border">
          {sessions.map((session) => (
            <div key={session.session_id} className="flex flex-wrap items-center justify-between gap-3 p-3">
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-surface-muted p-2">
                  {getDeviceIcon(session.device_family)}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-dark">
                      {session.browser_family || 'Navegador'} en {session.os_family || 'Dispositivo'}
                    </span>
                    {session.is_current && (
                      <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                        Sesión actual
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-[11px] text-muted">
                    IP: {session.ip_address || 'Protegida'} · Iniciada: {formatSessionDate(session.created_at)} · Última actividad: {formatSessionDate(session.last_activity_at)}
                  </p>
                </div>
              </div>

              {!session.is_current ? (
                <button
                  type="button"
                  disabled={revokeMutation.isPending}
                  onClick={() => handleRevokeSingle(session.session_id)}
                  className="rounded border border-border px-3 py-1 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50"
                >
                  Cerrar sesión
                </button>
              ) : (
                <span className="text-[11px] font-medium text-muted">Este equipo</span>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export default SessionManagementPanel;
