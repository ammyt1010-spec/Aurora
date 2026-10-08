import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useAuth } from '../auth/AuthContext.jsx';
import { ApiError } from '../api/client.js';
import { BrandMark } from '../brand/BrandMark.jsx';
import FormField from '../components/ui/FormField.jsx';
import { Button } from '../components/ui/Button.jsx';

const schema = z
  .object({
    firstName: z.string().min(1, 'Ingresa tu nombre'),
    lastName: z.string().optional(),
    email: z.string().email('Ingresa un email válido'),
    username: z.string().min(3, 'Mínimo 3 caracteres').max(120),
    password: z.string().min(8, 'Mínimo 8 caracteres'),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Las contraseñas no coinciden',
    path: ['confirmPassword'],
  });

export default function SignupPage() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [formError, setFormError] = useState(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema) });

  const onSubmit = async (values) => {
    setFormError(null);
    try {
      await signup(values);
      navigate('/login', { state: { justRegistered: true } });
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setFormError('Ya existe una cuenta con ese email o username.');
      } else if (error instanceof ApiError && error.body?.detail) {
        setFormError('Revisa los datos ingresados.');
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

        <form className="flex flex-col gap-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField label="Nombre" error={errors.firstName?.message} {...register('firstName')} />
            <FormField label="Apellido" error={errors.lastName?.message} {...register('lastName')} />
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
        </form>

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
