import { useState } from 'react';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { ShieldCheck } from 'lucide-react';

import { listOrganizations } from '../../api/organizations.js';
import { listOrganizationAuditEvents } from '../../api/audit.js';
import { Card } from '../ui/Card.jsx';

const EVENT_NAMES = {
  ORGANIZATION_CREATED: 'Empresa registrada',
  ORGANIZATION_MEMBER_JOINED: 'Colaborador incorporado',
  COLLABORATOR_CODE_CREATED: 'Invitación generada',
  COLLABORATOR_CODE_REVOKED: 'Invitación revocada',
  PROJECT_CREATED: 'Proyecto creado',
  PROJECT_UPDATED: 'Proyecto modificado',
  PROJECT_MEMBER_ADDED: 'Integrante incorporado',
  PROJECT_MEMBER_ROLE_CHANGED: 'Permisos modificados',
  PROJECT_MEMBER_REMOVED: 'Integrante retirado',
  REPORT_DOWNLOADED: 'Informe descargado',
  REPORT_PREVIEW_OPENED: 'Vista previa de informe',
  EXPORT_DOWNLOADED: 'Datos exportados',
};

function formatEventDate(value) {
  if (!value) return 'Fecha no disponible';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Fecha no disponible';
  return new Intl.DateTimeFormat('es-PE', {
    dateStyle: 'short', timeStyle: 'short',
  }).format(date);
}

export function EnterpriseAuditPanel() {
  const [selectedOrganizationId, setSelectedOrganizationId] = useState(null);
  const { data: memberships = [], isPending: loadingOrganizations, isError: organizationsError } = useQuery({
    queryKey: ['enterprise-audit-organizations'],
    queryFn: listOrganizations,
    retry: false,
  });
  const managedOrganizations = memberships.filter(
    (entry) => ['OWNER', 'ADMIN'].includes(entry.role_code),
  );
  const activeOrganizationId = managedOrganizations.some(
    (entry) => entry.organization.id === selectedOrganizationId,
  ) ? selectedOrganizationId : managedOrganizations[0]?.organization.id;

  const {
    data, isPending, isError, fetchNextPage,
    hasNextPage, isFetchingNextPage, refetch,
  } = useInfiniteQuery({
    queryKey: ['enterprise-audit-events', activeOrganizationId],
    initialPageParam: null,
    queryFn: ({ pageParam }) => listOrganizationAuditEvents(activeOrganizationId, {
      limit: 30, beforeId: pageParam,
    }),
    getNextPageParam: (page) => page.next_before_id ?? undefined,
    enabled: activeOrganizationId != null,
    retry: false,
  });
  const events = data?.pages.flatMap((page) => page.items) || [];

  if (loadingOrganizations) return null;
  if (organizationsError) {
    return <Card className="p-5"><p role="alert" className="text-sm text-red-700">No se pudieron consultar tus empresas.</p></Card>;
  }
  if (managedOrganizations.length === 0) return null;

  return (
    <Card className="space-y-4 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-base font-bold text-dark">
            <ShieldCheck size={18} /> Historial de actividad empresarial
          </h2>
          <p className="mt-1 text-xs text-muted">
            Registro de operaciones administrativas. Solo visible para administradores de esta empresa.
            No contiene contraseñas ni respuestas de trabajadores.
          </p>
        </div>
        <button type="button" onClick={() => refetch()} disabled={isPending}
          className="rounded-lg border border-border px-3 py-2 text-xs font-semibold text-dark disabled:opacity-50">
          Actualizar
        </button>
      </div>
      {managedOrganizations.length > 1 && (
        <label className="block text-xs font-semibold text-dark">
          Empresa
          <select className="colmena-input mt-1 block w-full max-w-lg"
            aria-label="Empresa para auditoría"
            value={activeOrganizationId}
            onChange={(event) => setSelectedOrganizationId(Number(event.target.value))}>
            {managedOrganizations.map((entry) => (
              <option key={entry.organization.id} value={entry.organization.id}>
                {entry.organization.name}
              </option>
            ))}
          </select>
        </label>
      )}
      {isPending && <p className="text-sm text-muted">Consultando actividad…</p>}
      {isError && <p role="alert" className="text-sm text-red-700">No se pudo obtener el historial de actividad.</p>}
      {!isPending && !isError && events.length === 0 && (
        <p className="text-sm text-muted">Todavía no hay eventos registrados para esta empresa.</p>
      )}
      {events.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-xs">
            <thead>
              <tr className="border-b border-border text-muted">
                <th className="px-2 py-2 font-semibold">Fecha</th>
                <th className="px-2 py-2 font-semibold">Actividad</th>
                <th className="px-2 py-2 font-semibold">Usuario</th>
                <th className="px-2 py-2 font-semibold">Proyecto</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {events.map((event) => (
                <tr key={event.id}>
                  <td className="whitespace-nowrap px-2 py-3 text-muted">{formatEventDate(event.created_at)}</td>
                  <td className="px-2 py-3 font-medium text-dark">
                    {EVENT_NAMES[event.action] || event.action.replaceAll('_', ' ')}
                  </td>
                  <td className="px-2 py-3 text-muted">{event.actor_user_id == null ? 'Sistema' : `#${event.actor_user_id}`}</td>
                  <td className="px-2 py-3 text-muted">{event.project_id == null ? 'Empresa' : `#${event.project_id}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {hasNextPage && (
        <button type="button" disabled={isFetchingNextPage} onClick={() => fetchNextPage()}
          className="rounded-lg border border-border px-4 py-2 text-xs font-semibold text-dark disabled:opacity-50">
          {isFetchingNextPage ? 'Cargando más…' : 'Mostrar eventos anteriores'}
        </button>
      )}
    </Card>
  );
}

export default EnterpriseAuditPanel;
