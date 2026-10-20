import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ArrowRight, BarChart3, FileCheck2, LockKeyhole, Shield, Sparkles } from 'lucide-react';

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
    <section className="relative min-h-screen overflow-hidden bg-slate-950 px-4 py-5 sm:px-6 lg:p-7">
      <div className="absolute -left-28 top-[-120px] h-[440px] w-[440px] rounded-full bg-violet-600/25 blur-[110px]" />
      <div className="absolute -right-20 bottom-[-140px] h-[420px] w-[420px] rounded-full bg-cyan-500/20 blur-[110px]" />

      <div className="relative z-10 mx-auto grid min-h-[calc(100vh-3.5rem)] max-w-[1420px] overflow-hidden rounded-[32px] border border-white/10 bg-white/[0.06] shadow-[0_35px_100px_rgba(0,0,0,0.38)] backdrop-blur-2xl lg:grid-cols-[1.15fr_.85fr]">
        <div className="relative hidden flex-col justify-between overflow-hidden p-10 lg:flex xl:p-14">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_20%,rgba(168,85,247,.18),transparent_38%),radial-gradient(circle_at_20%_80%,rgba(34,211,238,.14),transparent_36%)]" />
          <BrandLogo className="relative z-10" inverted />

          <div className="relative z-10 max-w-2xl">
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.07] px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.16em] text-cyan-200">
              <Sparkles size={13} /> Inteligencia psicosocial para decisiones reales
            </div>
            <h1 className="text-5xl font-black leading-[1.05] tracking-[-0.045em] text-white xl:text-6xl">
              Entender el riesgo. Actuar con evidencia.
            </h1>
            <p className="mt-5 max-w-xl text-[15px] leading-7 text-slate-300">
              Una sola plataforma para aplicar CENSOPAS, monitorear la participación, interpretar resultados y generar el expediente técnico.
            </p>
            <div className="mt-8 grid max-w-xl gap-3 sm:grid-cols-3">
              {[
                [LockKeyhole, 'Anonimato', 'Protección por diseño'],
                [BarChart3, 'Analítica', 'Métodos avanzados'],
                [FileCheck2, 'Reporte', 'Expediente técnico'],
              ].map(([Icon, title, copy]) => (
                <div key={title} className="rounded-2xl border border-white/10 bg-white/[0.06] p-3.5">
                  <Icon size={17} className="text-cyan-300" />
                  <p className="mt-3 text-xs font-extrabold text-white">{title}</p>
                  <p className="mt-1 text-[10px] text-slate-400">{copy}</p>
                </div>
              ))}
            </div>
          </div>

          <p className="relative z-10 text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">Diseñado para empresas peruanas · Ley 29783</p>
        </div>

        <div className="flex items-center justify-center bg-white px-5 py-8 sm:px-10 lg:px-12">
          <div className="w-full max-w-md">
            <div className="mb-8 lg:hidden"><BrandLogo /></div>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-violet-50 px-3 py-1.5 text-[10px] font-extrabold uppercase tracking-[0.12em] text-violet-700">
              <Shield size={12} /> Acceso de evaluación
            </span>
            <h2 className="mt-4 text-3xl font-black tracking-[-0.035em] text-slate-950">Explora Aurora sin credenciales.</h2>
            <p className="mt-3 text-sm leading-6 text-slate-500">Entra al entorno de demostración y crea el primer informe completo de tu empresa sin costo.</p>

            {formError ? <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-600">{formError}</p> : null}

            <Button type="button" variant="primary" onClick={handleDemoClick} className="mt-6 h-12 w-full border-none bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 text-white shadow-xl shadow-violet-500/20 hover:brightness-105">
              Entrar a Aurora <ArrowRight size={16} />
            </Button>
            <p className="mt-3 text-center text-[10px] font-semibold text-slate-400">Sin contraseña · Sin tarjeta · Acceso inmediato</p>

            <details className="group mt-7 rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
              <summary className="cursor-pointer text-xs font-bold text-slate-600">Acceso corporativo con credenciales</summary>
              <form className="mt-4 flex flex-col gap-4" onSubmit={handleSubmit(onSubmit)} noValidate>
                <FormField label="Email" type="email" autoComplete="email" error={errors.email?.message} {...register('email')} />
                <FormField label="Contraseña" type="password" autoComplete="current-password" error={errors.password?.message} {...register('password')} />
                <Button type="submit" variant="secondary" loading={isSubmitting} className="w-full">Ingresar con mi cuenta</Button>
              </form>
              <p className="mt-4 text-center text-[11px] text-slate-500">
                ¿Primera vez? <Link to="/signup" className="font-bold text-violet-700 hover:underline">Crear cuenta empresarial</Link>
              </p>
            </details>

            <div className="mt-7 flex items-center justify-center gap-2 text-[10px] font-semibold text-slate-400">
              <Shield className="h-3.5 w-3.5" /> Datos protegidos · Sesión cifrada
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
