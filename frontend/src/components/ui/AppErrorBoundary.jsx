import { Component } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

import { Button } from './Button.jsx';

export class AppErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    if (import.meta.env.DEV) console.error('Error de renderizado en Aurora', error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <main className="flex min-h-screen items-center justify-center bg-hero-glow p-4">
        <section className="w-full max-w-lg rounded-2xl border border-danger/20 bg-white p-5 text-center shadow-card">
          <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-danger/10 text-danger">
            <AlertTriangle size={20} />
          </div>
          <h1 className="mt-3 text-lg font-bold text-dark">No pudimos mostrar esta página</h1>
          <p className="mt-1 text-sm leading-5 text-muted">
            Recarga la aplicación. Si el problema continúa, revisa el detalle técnico en la consola.
          </p>
          <Button className="mt-4" onClick={() => window.location.reload()}>
            <RefreshCw size={15} />
            Recargar
          </Button>
        </section>
      </main>
    );
  }
}

export default AppErrorBoundary;
