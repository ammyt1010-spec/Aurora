import { useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart3,
  Building2,
  ChevronRight,
  Copy,
  ExternalLink,
  FileBarChart2,
  FolderKanban,
  Link as LinkIcon,
  QrCode,
  ShieldCheck,
  Sparkles,
  Users,
} from 'lucide-react';

import { getProject } from '../../../api/projects.js';

export default function ProjectWorkspaceHeader({ activeTab = 'link' }) {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [copied, setCopied] = useState(false);

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
    enabled: Boolean(projectId),
  });

  const publicId = project?.censopas_study?.public_id || project?.metadata_?.public_id;
  const surveyUrl = publicId ? `${window.location.origin}/encuesta/${publicId}` : null;

  const handleCopy = () => {
    if (!surveyUrl) return;
    navigator.clipboard.writeText(surveyUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const navTabs = [
    {
      id: 'link',
      label: '1. Enlace & Código QR',
      icon: LinkIcon,
      path: `/colmena/project/${projectId}/link`,
    },
    {
      id: 'telemetry',
      label: '2. Telemetría en Vivo',
      icon: BarChart3,
      path: `/colmena/project/${projectId}/telemetry`,
    },
    {
      id: 'reports',
      label: '3. Informes profesionales',
      icon: FileBarChart2,
      path: `/colmena/project/${projectId}/reports`,
    },
    {
      id: 'team',
      label: '4. Colaboradores',
      icon: Users,
      path: `/colmena/project/${projectId}/team`,
    },
  ];

  return (
    <div className="mb-4 space-y-3 text-xs">
      {/* High-Density Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-border bg-surface p-3.5 shadow-sm">
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-muted">
            <Link to="/colmena" className="hover:text-amber transition flex items-center gap-1">
              <FolderKanban size={12} /> Menú de Instrumentos
            </Link>
            <ChevronRight size={11} />
            <span className="text-dark font-bold">{project?.name || 'Cargando...'}</span>
          </div>

          <div className="flex items-center gap-2">
            <h1 className="text-base font-extrabold text-dark tracking-tight">
              {project?.name || 'Evaluación Psicosocial'}
            </h1>
            {project?.censopas_study?.workplace_name ? (
              <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber bg-amber/10 border border-amber/20 px-2 py-0.5 rounded-full">
                <Building2 size={11} />
                {project.censopas_study.workplace_name}
              </span>
            ) : null}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2 shrink-0">
          {surveyUrl ? (
            <>
              <button
                type="button"
                onClick={handleCopy}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-border bg-surfaceSoft hover:bg-surface text-dark font-bold text-xs transition"
              >
                <Copy size={12} className="text-amber" />
                {copied ? '¡Copiado!' : 'Copiar Link'}
              </button>
              <a
                href={surveyUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-border bg-surfaceSoft hover:bg-surface text-dark font-semibold text-xs transition"
              >
                <ExternalLink size={12} />
                Probar Encuesta
              </a>
            </>
          ) : null}
        </div>
      </div>

      {/* 3-Step Navigation Tabs */}
      <div className="flex border-b border-border bg-surface/60 rounded-xl p-1 gap-1">
        {navTabs.map((tab) => {
          const isActive = location.pathname.includes(tab.id);
          const Icon = tab.icon;
          return (
            <Link
              key={tab.id}
              to={tab.path}
              className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-bold transition ${
                isActive
                  ? 'bg-amber text-dark shadow-sm'
                  : 'text-muted hover:text-dark hover:bg-surfaceSoft'
              }`}
            >
              <Icon size={14} className={isActive ? 'text-dark' : 'text-muted'} />
              <span>{tab.label}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
