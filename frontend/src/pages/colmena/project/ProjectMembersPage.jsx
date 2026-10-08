import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, ShieldCheck, Trash2, Users } from 'lucide-react';

import { useAuth } from '../../../auth/AuthContext.jsx';
import { getProject, listProjectMembers, addProjectMemberByEmail, removeProjectMember } from '../../../api/projects.js';
import { useActiveProject } from '../../../hooks/useActiveProject.js';
import ProjectWorkspaceHeader from '../../../components/colmena/project/ProjectWorkspaceHeader.jsx';
import { Card } from '../../../components/ui/Card.jsx';
import { LoadingState } from '../../../components/ui/LoadingState.jsx';
import { ProjectMissingState } from '../../../components/colmena/ProjectMissingState.jsx';

const ROLES = [
  { value: 'VIEWER', label: 'Lector (sin modificaciones)' },
  { value: 'EDITOR', label: 'Editor (puede trabajar en el proyecto)' },
  { value: 'ADMIN', label: 'Administrador (gestiona miembros)' },
];

export default function ProjectMembersPage() {
  const { projectId } = useParams();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [email, setEmail] = useState('');
  const [roleCode, setRoleCode] = useState('VIEWER');
  const [message, setMessage] = useState('');
  useActiveProject(projectId);

  const { data: project, isLoading } = useQuery({
    queryKey: ['project', projectId], queryFn: () => getProject(projectId),
  });
  const { data: members = [], isLoading: membersLoading } = useQuery({
    queryKey: ['projectMembers', projectId], queryFn: () => listProjectMembers(projectId),
    enabled: Boolean(projectId),
  });
  const update = useMutation({
    mutationFn: () => addProjectMemberByEmail(projectId, email.trim(), roleCode),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['projectMembers', projectId] });
      setEmail('');
      setMessage('Colaborador registrado correctamente.');
    },
    onError: () => setMessage('No se pudo invitar a esa cuenta. Comprueba que esté registrada y tus permisos.'),
  });
  const remove = useMutation({
    mutationFn: (userId) => removeProjectMember(projectId, userId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['projectMembers', projectId] });
      setMessage('Acceso del colaborador revocado.');
    },
    onError: () => setMessage('No fue posible revocar ese acceso.'),
  });

  if (isLoading) return <LoadingState label="Cargando proyecto..." />;
  if (!project) return <ProjectMissingState />;

  return (
    <div className="colmena-page space-y-5">
      <ProjectWorkspaceHeader activeTab="team" />
      <div className="flex items-center gap-2">
        <Users size={21} className="text-amber" />
        <div>
          <h2 className="text-xl font-bold text-dark">Equipo profesional</h2>
          <p className="text-xs text-muted">Los permisos se verifican en el servidor; no dependen de esta pantalla.</p>
        </div>
      </div>
      <Card className="space-y-4">
        <h3 className="text-sm font-bold text-dark">Agregar colaborador</h3>
        <form className="flex flex-wrap gap-3" onSubmit={(event) => {
          event.preventDefault();
          setMessage('');
          update.mutate();
        }}>
          <input aria-label="Correo electrónico del colaborador" type="email" required
            value={email} onChange={(event) => setEmail(event.target.value)}
            placeholder="correo@empresa.com"
            className="colmena-input min-w-[220px] flex-1" />
          <select aria-label="Permiso" className="colmena-input" value={roleCode}
            onChange={(event) => setRoleCode(event.target.value)}>
            {ROLES.map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}
          </select>
          <button type="submit" disabled={update.isPending || !email.trim()}
            className="inline-flex items-center gap-2 rounded-xl bg-amber px-4 py-2 text-sm font-bold text-dark disabled:opacity-50">
            <Plus size={16} /> {update.isPending ? 'Agregando…' : 'Agregar'}
          </button>
        </form>
        {message ? <p role="status" className="text-xs text-muted">{message}</p> : null}
      </Card>
      <Card>
        <h3 className="mb-3 text-sm font-bold text-dark">Personas con acceso al proyecto</h3>
        {membersLoading ? <LoadingState label="Consultando colaboradores…" /> : (
          <div className="divide-y divide-border">
            {members.map((member) => (
              <div className="flex flex-wrap items-center justify-between gap-3 py-3" key={member.user_id}>
                <div>
                  <p className="text-sm font-semibold text-dark">{member.username || `Usuario ${member.user_id}`}</p>
                  <p className="text-xs text-muted">
                    {member.role_code === 'OWNER' ? 'Propietario' :
                      ROLES.find((role) => role.value === member.role_code)?.label || member.role_code}
                    {member.user_id === user?.id ? ' · Tú' : ''}
                  </p>
                </div>
                {member.role_code === 'OWNER' ? <ShieldCheck size={17} className="text-turquoise" /> : (
                  <button type="button" onClick={() => {
                    if (window.confirm('¿Revocar el acceso de este colaborador?')) remove.mutate(member.user_id);
                  }} disabled={remove.isPending} aria-label={`Eliminar a ${member.username}`}
                    className="rounded-lg border border-border p-2 text-danger hover:bg-red-50">
                    <Trash2 size={16} />
                  </button>
                )}
              </div>
            ))}
            {!members.length ? <p className="py-4 text-xs text-muted">Sin colaboradores registrados.</p> : null}
          </div>
        )}
      </Card>
    </div>
  );
}
