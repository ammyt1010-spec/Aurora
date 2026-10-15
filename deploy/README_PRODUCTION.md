# AURORA: despliegue para preproducción

**No publicar el servidor de desarrollo de Vite como aplicación empresarial.**
Este ejemplo requiere completar las pruebas de seguridad, PostgreSQL, biometría
(si se añade), informe y cumplimiento legal antes de permitir datos reales.

1. Preparar `backend/.env`: `ENVIRONMENT=production`,
   `JWT_SECRET_KEY` aleatoria con 48 caracteres o más, credenciales únicas
   `DATABASE_URL` / `DATABASE_URL_SYNC`; mantener `DEMO_ACCESS_ENABLED=false`.
2. Aplicar migraciones Alembic después de respaldar y ensayar restauración en
   PostgreSQL real. No reutilizar contraseñas de desarrollo.
3. Instalar LibreOffice y verificar que `soffice` esté disponible para el
   usuario de servicio. Sin él, el backend debe informar un fallo de PDF.
4. Corregir y confirmar `frontend/package-lock.json`. Ejecutar
   `npm ci && npm run build` con `VITE_API_BASE_URL=/api/v1`.
5. Ejecutar la API FastAPI en `127.0.0.1:8001`; servir
   `frontend/dist` desde Caddy con `deploy/Caddyfile`.
6. Publicar HTTPS delante del proxy de puerto 8080. Configurar dominios y
   orígenes CORS restringidos. No exponer el puerto 8001.
7. Controlar permisos de archivos, retención, cifrado de copias de seguridad,
   logs, métricas y restauración periódica.
8. Realizar pruebas de roles con dos empresas, invitaciones, descargas y
   protección de grupos estadísticos pequeños.

**Advertencia:** `install-colmena-services.ps1` es heredado y usa Vite de
desarrollo. No usarlo como receta de producción profesional.
