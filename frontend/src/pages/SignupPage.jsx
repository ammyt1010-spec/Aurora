import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ApiError } from '../api/client.js';
import { BrandMark } from '../brand/BrandMark.jsx';
import FormField from '../components/ui/FormField.jsx';
import { Button } from '../components/ui/Button.jsx';
import { useQuery } from '@tanstack/react-query';
import { getRegistrationPolicy, signupCompanyAccount, resendCompanyVerification } from '../api/auth.js';

const schema = z
  .object({
    companyName: z.string().trim().min(2, 'Ingresa la razón social'),
    companyRuc: z.string().regex(/^\d{11}$/, 'El RUC debe tener 11 dígitos'),
    companyWorkers: z.coerce.number().int().min(1, 'Ingresa la dotación de trabajadores'),
    email: z.string().email('Ingresa un email válido'),
    username: z.string().min(3, 'Mínimo 3 caracteres').max(120),
    password: z.string().min(12, 'Mínimo 12 caracteres'),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Las contraseñas no coinciden',
    path: ['confirmPassword'],
  });

export default function SignupPage() {
  const { data: registrationPolicy } = useQuery({ queryKey: ['registration-policy'], queryFn: getRegistrationPolicy, retry: false });
  const navigate = useNavigate();
  const [formError, setFormError] = useState(null);
  const [registeredEmail, setRegisteredEmail] = useState(null);
  const [resent, setResent] = useState(false);
  const [resendWait, setResendWait] = useState(0);

  useEffect(() => {
    if (resendWait <= 0) return undefined;
    const timer = window.setTimeout(() => setResendWait((remaining) => remaining - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [resendWait]);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema) });

  const onSubmit = async (values) => {
    setFormError(null);
    try {
      const result = await signupCompanyAccount({
        email: values.email, username: values.username, password: values.password,
        company_name: values.companyName, company_ruc: values.companyRuc,
        company_workers: values.companyWorkers,
      });
      if (result.verification_required) {
        setRegisteredEmail(values.email);
        setResendWait(60);
      }
      else navigate('/login', { state: { justRegistered: true } });
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setFormError('Ya existe una cuenta con ese email o username.');
      } else if (error instanceof ApiError && error.status === 403) {
        setFormError('El registro está cerrado temporalmente. Solicita acceso al administrador de AURORA.');
      } else if (error instanceof ApiError && error.status === 429) {
        setFormError('Demasiados intentos. Espera unos minutos y vuelve a probar.');
      } else if (error instanceof ApiError && error.status === 503) {
        setFormError('El correo de confirmación no está disponible. Inténtalo de nuevo en unos minutos.');
      } else {
        setFormError('No pudimos crear tu cuenta. Intenta de nuevo.');
      }
    }
  };

  return (
    <section className="relative flex min-h-screen items-center justify-center overflow-hidden bg-hero-glow px-4 py-6 sm:px-6">
      <div className="colmena-card relative z-10 w-full max-w-lg px-6 py-7 sm:px-8 sm:py-8">
        <div className="mx-auto mb-5 flex flex-col items-center gap-2">
          <BrandMark className="h-10 w-10" />
          <h1 className="text-xl font-bold text-dark">Crea tu cuenta en AURORA PRO</h1>
          <p className="text-center text-sm text-muted">Plataforma Profesional de Evaluación de Riesgos Psicosociales y Salud Ocupacional.</p>
        </div>

        {registeredEmail ? (
          <div className="rounded-xl bg-[#EDF9FB] px-4 py-4 text-center text-sm text-[#075A70]">
            <p className="font-semibold">Confirma tu correo para activar la cuenta</p>
            <p className="mt-2">Enviamos un enlace a {registeredEmail}. Vence en 24 horas.</p>
            <button type="button" disabled={resendWait > 0} className="mt-3 font-semibold underline disabled:cursor-not-allowed disabled:opacity-50" onClick={async () => {
              try { await resendCompanyVerification(registeredEmail); setResent(true); setResendWait(60); }
              catch { setFormError('No pudimos reenviar el mensaje. Espera unos minutos.'); }
            }}>{resendWait > 0 ? `Reenviar en ${resendWait} s` : 'Reenviar correo'}</button>
            {resent ? <p className="mt-2">Si la cuenta aún está pendiente, recibirás un nuevo enlace.</p> : null}
            {formError ? <p className="mt-2 text-danger">{formError}</p> : null}
          </div>
        ) : registrationPolicy?.self_registration_enabled !== true ? (
          <p className="rounded-xl bg-[#EDF9FB] px-4 py-4 text-center text-sm font-medium text-[#075A70]">
            Las cuentas empresariales se entregan de forma privada. Solicita tus credenciales al administrador de AURORA.
          </p>
        ) : <form className="flex flex-col gap-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          <FormField label="Razón social" error={errors.companyName?.message} {...register('companyName')} />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField label="RUC" inputMode="numeric" maxLength={11} error={errors.companyRuc?.message} {...register('companyRuc')} />
            <FormField label="Trabajadores" type="number" min="1" error={errors.companyWorkers?.message} {...register('companyWorkers')} />
          </div>

          <FormField
            label="Email"
            type="email"
            autoComplete="email"
            error={errors.email?.message}
            {...register('email')}
          />
          <FormField
            label="Usuario"
            autoComplete="username"
            error={errors.username?.message}
            {...register('username')}
          />

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField
              label="Contraseña"
              type="password"
              autoComplete="new-password"
              error={errors.password?.message}
              {...register('password')}
            />
            <FormField
              label="Confirmar contraseña"
              type="password"
              autoComplete="new-password"
              error={errors.confirmPassword?.message}
              {...register('confirmPassword')}
            />
          </div>

          {formError ? (
            <p className="rounded-xl bg-red-50 px-4 py-3 text-sm font-medium text-danger">{formError}</p>
          ) : null}

          <Button type="submit" variant="primary" loading={isSubmitting} className="mt-2 w-full">
            Crear cuenta
          </Button>
        </form>}

        <p className="mt-4 text-center text-sm text-muted">
          ¿Ya tienes cuenta?{' '}
          <Link to="/login" className="font-semibold text-amber hover:underline">
            Inicia sesión
          </Link>
        </p>
      </div>
    </section>
  );
}
