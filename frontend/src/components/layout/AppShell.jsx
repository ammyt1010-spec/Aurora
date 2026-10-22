import { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';

import { Sidebar } from './Sidebar.jsx';
import { MobileJourneyNav } from './MobileJourneyNav.jsx';
import { Topbar } from './Topbar.jsx';
import { ColmenaMenuButton } from './ColmenaMenuButton.jsx';

/**
 * Shell raíz portado de fullProyect/COLMENA/frontend (AppShell.tsx) — mismo
 * criterio de "ruta workspace" (edge-to-edge) adaptado a nuestro prefijo
 * real /colmena/project/:id en vez de /project/:id.
 */
export function AppShell() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const isProjectWorkspace = location.pathname.startsWith('/colmena/project/');
  const isWorkspace =
    isProjectWorkspace ||
    location.pathname.includes('/new') ||
    location.pathname.includes('/workspace') ||
    location.pathname.includes('/builder') ||
    location.pathname.includes('/form');

  return (
    <div className="min-h-screen bg-transparent pb-16 lg:pb-0">
      <div className="flex min-h-screen">
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
        <div className="flex min-h-screen min-w-0 flex-1 flex-col">
          <Topbar />
          <main className={isWorkspace ? 'flex min-w-0 flex-1 flex-col overflow-x-hidden' : 'flex-1'}>
            {isWorkspace ? (
              <Outlet />
            ) : (
              <div className="mx-auto flex w-full flex-col">
                <Outlet />
              </div>
            )}
          </main>
        </div>
      </div>

      <MobileJourneyNav />

      {collapsed && (
        <ColmenaMenuButton
          onClick={() => setCollapsed(false)}
          title="Mostrar menú"
          className="fixed left-3 top-3 z-30 hidden rounded-xl border border-[#E6E8EB] bg-white/95 p-2.5 shadow-sm backdrop-blur transition hover:border-amber/40 hover:shadow-md lg:flex"
        />
      )}
    </div>
  );
}

export default AppShell;
