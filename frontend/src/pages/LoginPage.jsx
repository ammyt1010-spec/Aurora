import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Shield } from 'lucide-react';

import { useAuth } from '../auth/AuthContext.jsx';
import { ApiError } from '../api/client.js';
import { BrandLogo } from '../brand/BrandLogo.jsx';
import FormField from '../components/ui/FormField.jsx';
import { Button } from '../components/ui/Button.jsx';

const schema = z.object({
  email: z.string().email('Ingresa un email válido'),
  password: z.string().min(1, 'Ingresa tu contraseña'),
});

export default function LoginPage() {
  const { login, demoLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [formError, setFormError] = useState(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema) });

  const handleDemoClick = async () => {
    try {
      await demoLogin();
      const redirectTo = location.state?.from?.pathname || '/colmena';
      navigate(redirectTo, { replace: true });
    } catch {
      setFormError('No se pudo iniciar el modo demostración sin credenciales.');
    }
  };

  const onSubmit = async (values) => {
    setFormError(null);
    try {
      await login(values);
      const redirectTo = location.state?.from?.pathname || '/colmena';
      navigate(redirectTo, { replace: true });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setFormError('Email o contraseña incorrectos.');
      } else {
        setFormError('No pudimos conectar con el sistema. Intenta de nuevo.');
      }
    }
  };

  return (
    <section className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-slate-50 via-white to-aurora-50 px-4 py-6 sm:px-6 dark:from-slate-950 dark:via-slate-900 dark:to-aurora-950">
      {/* Decorative Blur Circles */}
      <div className="absolute top-10 left-10 h-64 w-64 rounded-full bg-aurora-400/20 mix-blend-multiply blur-3xl filter dark:bg-aurora-600/20 dark:mix-blend-screen" />
      <div className="absolute bottom-10 right-10 h-72 w-72 rounded-full bg-cyan-400/20 mix-blend-multiply blur-3xl filter dark:bg-cyan-600/20 dark:mix-blend-screen" />

      <div className="colmena-card animate-slide-up relative z-10 w-full max-w-md px-6 py-8 sm:px-8 shadow-glass border border-white/40 dark:border-slate-800/60 dark:bg-slate-900/60 backdrop-blur-xl">
        <div className="mx-auto mb-8 flex flex-col items-center gap-4">
          <div className="relative">
            <div className="absolute -inset-1 rounded-full bg-gradient-to-r from-aurora-400 to-cyan-400 opacity-70 blur filter animate-glow-pulse dark:opacity-40" />
            <BrandLogo className="relative h-12 w-auto scale-110" />
          </div>
          <p className="text-center text-sm font-medium text-slate-500 dark:text-slate-400">
            Plataforma Profesional de Evaluación
          </p>
        </div>

        <Button 
          type="button" 
          variant="primary" 
          onClick={handleDemoClick} 
          className="w-full bg-gradient-to-r from-aurora-500 to-aurora-600 hover:from-aurora-600 hover:to-aurora-700 shadow-aurora-500/25 border-none text-white transition-all transform hover:-translate-y-0.5 hover:shadow-lg dark:from-aurora-600 dark:to-aurora-700"
        >
          Acceder al Sistema
        </Button>

        <div className="my-6 flex items-center">
          <div className="flex-1 border-t border-slate-200 dark:border-slate-700"></div>
          <span className="mx-4 text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            o ingresa con tu cuenta
          </span>
          <div className="flex-1 border-t border-slate-200 dark:border-slate-700"></div>
        </div>

        <form className="flex flex-col gap-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          <FormField 
            label="Email" 
            type="email" 
            autoComplete="email" 
            error={errors.email?.message} 
            {...register('email')} 
          />
          <FormField
            label="Contraseña"
            type="password"
            autoComplete="current-password"
            error={errors.password?.message}
            {...register('password')}
          />

          {formError ? (
            <p className="rounded-xl bg-red-50/50 px-4 py-3 text-sm font-medium text-red-600 dark:bg-red-900/20 dark:text-red-400">
              {formError}
            </p>
          ) : null}

          <Button 
            type="submit" 
            variant="secondary" 
            loading={isSubmitting} 
            className="mt-2 w-full dark:bg-slate-800/50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-700/50"
          >
            Ingresar con credenciales
          </Button>
        </form>

        <div className="mt-8 flex items-center justify-center gap-2 text-xs font-medium text-slate-400 dark:text-slate-500">
          <Shield className="h-3.5 w-3.5" />
          <span>Plataforma segura &middot; Datos protegidos</span>
        </div>
      </div>
    </section>
  );
}
