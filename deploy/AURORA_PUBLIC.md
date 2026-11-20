# AURORA en `aurora.aeia.top`

La publicación actual sigue la infraestructura local de Appthesis: un túnel
Cloudflare **permanente** lleva `aurora.aeia.top` a `127.0.0.1:8302`. El servidor
Node sirve la compilación React y envía `/api` y `/health` a FastAPI en
`127.0.0.1:8004`. PostgreSQL permanece en el equipo Windows. No se usa un
túnel temporal ni se incluyen secretos en Git.

## Puesta en marcha

1. Mantener Windows, PostgreSQL y el conector Cloudflare en funcionamiento.
2. Crear `backend/.env.public` privado con `ENVIRONMENT=staging`,
   `DEMO_ACCESS_ENABLED=false`, una clave JWT aleatoria de al menos 48
   caracteres, `SELF_REGISTRATION_ENABLED=true`,
   `EMAIL_VERIFICATION_REQUIRED=true`, `RESEND_API_KEY` restringida al dominio
   verificado, `EMAIL_FROM=AURORA <cuentas@aeia.top>`,
   `PUBLIC_APP_URL=https://aurora.aeia.top` y `BILLING_OPERATOR_USER_ID` real.
   Las URL de PostgreSQL pueden venir de `backend/.env` o del entorno.
3. Aplicar las migraciones Alembic, instalar dependencias Python y compilar
   React con `npm run build` en `frontend/`.
4. Ejecutar `deploy/start-aurora-public.ps1` con PowerShell 7; el script arranca
   solo los procesos que faltan. `Aurora Public Link` inicia al entrar a
   Windows y `Aurora-User-Watchdog` repite el chequeo cada cinco minutos.
5. Comprobar `https://aurora.aeia.top/health/ready`, `/signup` y el flujo de
   verificación por correo antes de invitar empresas.

La tarea de vigilancia está configurada para la sesión interactiva del usuario.
Si el equipo se apaga o Windows queda sin una sesión iniciada, AURORA deja de
estar disponible. Un servicio independiente del equipo requiere migrar API y
PostgreSQL a un host permanente y configurar supervisión de procesos allí.

## Seguridad y operación

- `backend/.env.public` y `backend/.env` están ignorados por Git; nunca copiar
  sus valores a incidencias o documentación pública.
- El registro crea una cuenta `PENDING_EMAIL`, sin acceso hasta confirmar el
  enlace enviado a su correo. El enlace vence en 24 horas y deja de servir al
  primer uso. El reenvío está limitado por IP, cuenta y tiempo.
- El administrador puede emitir cuentas, suspenderlas y restablecer credenciales
  desde Configuración. Los cuatro usos gratuitos se contabilizan por cuenta.
- El RUC se captura, pero su titularidad no se valida automáticamente; una
  cuenta confirmada por correo no equivale a una empresa verificada. Revisar
  razón social, RUC, responsables y firmas antes de emitir un expediente oficial.
- Los datos bancarios de ejemplo siguen siendo provisionales. Sustituirlos y
  verificar el flujo de cobro antes de aceptar pagos reales.
