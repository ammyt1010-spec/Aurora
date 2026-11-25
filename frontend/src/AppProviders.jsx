import { useState } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { MutationCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';

import App from './App.jsx';
import { AuthProvider } from './auth/AuthContext.jsx';
import { AppErrorBoundary } from './components/ui/AppErrorBoundary.jsx';
import { useToast } from './components/ui/Toast.jsx';

/**
 * El `QueryClient` se crea aquí (no en main.jsx) porque su `MutationCache`
 * necesita `useToast()` — un hook, así que requiere estar dentro de
 * `ToastProvider` (D-20: notificar cualquier error de mutación sin que cada
 * componente tenga que cablear su propio manejo de error). Componentes que
 * ya muestran su error inline pueden apagar el toast global con
 * `useMutation({ meta: { skipGlobalToast: true } })`.
 */
export function AppProviders() {
  const { showApiError } = useToast();
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: 1, refetchOnWindowFocus: false },
        },
        mutationCache: new MutationCache({
          onError: (error, _variables, _context, mutation) => {
            if (mutation.options?.meta?.skipGlobalToast) return;
            showApiError(error);
          },
        }),
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, '') || '/'} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <AppErrorBoundary>
          <AuthProvider>
            <App />
          </AuthProvider>
        </AppErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default AppProviders;
