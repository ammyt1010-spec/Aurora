import { Link } from 'react-router-dom';

import { EmptyState } from '../../components/ui/EmptyState.jsx';

export default function NotFoundPage() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 px-4 py-16 sm:px-8">
      <EmptyState title="Página no encontrada" description="La ruta solicitada no existe dentro de Aurora.">
        <Link to="/colmena" className="colmena-button-primary">
          Volver al dashboard
        </Link>
      </EmptyState>
    </div>
  );
}
