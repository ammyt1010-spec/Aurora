import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BrandMark } from '../brand/BrandMark.jsx';
import { verifyCompanyEmail } from '../api/auth.js';
import { Button } from '../components/ui/Button.jsx';

export default function VerifyEmailPage() {
  const [token] = useState(() => new URLSearchParams(window.location.search).get('token'));
  const [state, setState] = useState('ready');

  useEffect(() => {
    if (token) window.history.replaceState(window.history.state, '', '/verify-email');
  }, [token]);

  const confirm = async () => {
    setState('loading');
    try {
      await verifyCompanyEmail(token);
      setState('success');
    } catch {
      setState('error');
    }
  };

  return <section className="relative flex min-h-screen items-center justify-center bg-hero-glow px-4">
    <div className="colmena-card w-full max-w-md px-7 py-8 text-center">
      <BrandMark className="mx-auto h-10 w-10" />
      <h1 className="mt-4 text-xl font-bold text-dark">Confirma tu cuenta AURORA</h1>
      {state === 'success' ? <p className="mt-4 text-sm text-muted">Correo confirmado. Ya puedes iniciar sesión y crear tu primera evaluación.</p>
        : state === 'error' || !token ? <p className="mt-4 text-sm text-danger">Este enlace es inválido, ya se usó o expiró. Solicita uno nuevo desde el registro.</p>
          : <p className="mt-4 text-sm text-muted">Activa tu cuenta empresarial para acceder a tus cuatro evaluaciones gratuitas.</p>}
      {state === 'ready' && token ? <Button type="button" variant="primary" className="mt-5 w-full" onClick={confirm}>Confirmar correo</Button> : null}
      {state === 'loading' ? <p className="mt-5 text-sm text-muted">Confirmando…</p> : null}
      <Link to="/login" className="mt-5 inline-block text-sm font-semibold text-amber hover:underline">Ir a iniciar sesión</Link>
    </div>
  </section>;
}
