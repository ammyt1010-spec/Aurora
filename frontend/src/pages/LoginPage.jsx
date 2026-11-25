import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Shield, BarChart3, ArrowLeft } from 'lucide-react';

import { useAuth } from '../auth/AuthContext.jsx';
import { ApiError } from '../api/client.js';
import { BrandLogo } from '../brand/BrandLogo.jsx';
import { BrandMark } from '../brand/BrandMark.jsx';
import AuroraProductPreview from './AuroraProductPreview.jsx';
import './LandingPage.css';
import FormField from '../components/ui/FormField.jsx';
import { Button } from '../components/ui/Button.jsx';
import { getRegistrationPolicy } from '../api/auth.js';

const schema = z.object({
  email: z.string().email('Ingresa un email válido'),
  password: z.string().min(1, 'Ingresa tu contraseña'),
});

export default function LoginPage() {
  const { login, demoLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [formError, setFormError] = useState(null);
  const { data: registrationPolicy } = useQuery({
    queryKey: ['registration-policy'], queryFn: getRegistrationPolicy, retry: false,
  });

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema) });

  const handleDemoClick = async (destinationPath = '/colmena/project/23/telemetry') => {
    try {
      await demoLogin();
      navigate(destinationPath, { replace: true });
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

  const isDemoAllowed = ['localhost', '127.0.0.1'].includes(window.location.hostname);

  return (
    <section className="aurora-auth">
      <div className="aurora-auth__frame">
        <aside className="aurora-auth__showcase">
          <Link to="/" className="aurora-auth__brand" aria-label="AURORA, volver al inicio"><BrandMark decorative className="h-10 w-11" /><span><strong>AURORA</strong><small>PROFESSIONAL</small></span></Link>
          <div className="aurora-auth__showcase-copy"><span>INTELIGENCIA EN SALUD OCUPACIONAL</span><h1>Una mejor forma de <em>entender los riesgos.</em></h1><p>Conecta la aplicación, el análisis por dimensiones y el informe técnico en una sola experiencia.</p></div>
          <div className="aurora-auth__preview"><AuroraProductPreview compact /></div>
          <p className="aurora-auth__showcase-foot">Una vista clara para decisiones importantes.</p>
        </aside>

        <div className="aurora-auth__form-area">
          <Link to="/" className="aurora-auth__back"><ArrowLeft size={16} /> Volver al inicio</Link>
          <div className="colmena-card animate-slide-up relative z-10 w-full max-w-md px-6 py-8 sm:px-8 shadow-glass border border-white/40 backdrop-blur-xl">
        <div className="mx-auto mb-8 flex flex-col items-center gap-4">
          <div className="relative">
            <div className="absolute -inset-1 rounded-full bg-gradient-to-r from-aurora-400 to-cyan-400 opacity-70 blur filter animate-glow-pulse dark:opacity-40" />
            <BrandLogo className="relative h-12 w-auto scale-110" />
          </div>
          <h2 className="text-center text-xl font-bold text-[#123652]">Bienvenido a AURORA</h2>
          <p className="text-center text-sm font-medium text-slate-500">Ingresa a tu espacio empresarial</p>
        </div>

        {isDemoAllowed && (
          <div className="space-y-2.5">
            <Button
              type="button"
              variant="primary"
              onClick={() => handleDemoClick('/colmena/project/23/telemetry')} 
              className="w-full bg-gradient-to-r from-teal-500 to-teal-600 hover:from-teal-600 hover:to-teal-700 shadow-md border-none text-white font-bold py-3 transition-all transform hover:-translate-y-0.5 flex items-center justify-center gap-2 text-sm"
            >
              <BarChart3 size={17} /> ⚡ Ver Demo Minera (Tablero y Telemetría)
            </Button>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => handleDemoClick('/colmena')}
                className="flex-1 rounded-lg border border-slate-200 bg-white/80 px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition text-center"
              >
                1. Inicio (Catálogo)
              </button>
              <button
                type="button"
                onClick={() => handleDemoClick('/colmena/project/23/reports')}
                className="flex-1 rounded-lg border border-slate-200 bg-white/80 px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition text-center"
              >
                3. Informe Ejecutivo
              </button>
            </div>
            <p className="text-center text-[11px] text-slate-500 leading-snug">
              Carga el estudio de la <strong>Unidad Minera San Cristóbal</strong> con 35 colaboradores sintéticos, cuestionario CENSOPAS oficial y tablero Power BI en vivo.
            </p>
          </div>
        )}

        {isDemoAllowed && <div className="my-6 flex items-center">
          <div className="flex-1 border-t border-slate-200"></div>
          <span className="mx-4 text-xs font-semibold uppercase tracking-wider text-slate-400">
            o ingresa con tu cuenta
          </span>
          <div className="flex-1 border-t border-slate-200"></div>
        </div>}

        <form className="flex flex-col gap-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          {location.state?.justRegistered && <p role="status" className="rounded-xl bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">Cuenta creada. Ingresa con el correo y la contraseña que elegiste.</p>}
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
            <p className="rounded-xl bg-red-50/50 px-4 py-3 text-sm font-medium text-red-600">
              {formError}
            </p>
          ) : null}

          <Button 
            type="submit" 
            variant="primary"
            loading={isSubmitting} 
            className="aurora-auth__submit mt-2 w-full"
          >
            Ingresar con credenciales
          </Button>
        </form>

        {registrationPolicy?.self_registration_enabled && (
          <p className="mt-5 text-center text-sm text-slate-600">
            ¿Tu empresa aún no tiene cuenta? <Link to="/signup" className="font-bold text-[#087D9B] underline">Crear cuenta</Link>
          </p>
        )}

        <div className="mt-8 flex items-center justify-center gap-2 text-xs font-medium text-slate-400">
          <Shield className="h-3.5 w-3.5" />
          <span>Plataforma segura &middot; Datos protegidos</span>
        </div>
          </div>
        </div>
      </div>
    </section>
  );
}
