# AURORA: estado del endurecimiento profesional

Rama: `hardening/aurora-professional-v1`.
Esta rama no se ha fusionado con `main`.

## Integrado

- Verificación JWT en los routers privados y autorización por proyecto para IDs de recursos.
- Acceso a respuestas mediante token JWT acotado a una sesión anónima o encargado autorizado.
- Invitaciones opcionales y bloqueo de consumo concurrente de códigos en PostgreSQL.
- Listado global de instrumentos filtrado y propiedad definida desde el usuario autenticado.
- Descarga autenticada de exportaciones y reportes, incluyendo vistas previas en la interfaz.
- Validación de relación entre análisis y estudio durante la generación de informes.
- Secretos fuertes obligatorios y demo deshabilitada en modo producción.
- Supresión adicional de totales cuando hay celdas pequeñas.
- Fail-closed de PDF si LibreOffice no puede convertir correctamente.
- Correcciones de rutas y proxy del frontend para desarrollo.

## Validación requerida

1. Revisar resultado de GitHub Actions, corregir las pruebas heredadas que asumían APIs abiertas.
2. Probar con PostgreSQL real, 2 empresas, diferentes usuarios y combinaciones de roles.
3. Comprobar flujo de estudio OPEN, invitación, respuesta y finalización; probar concurrencia de invitaciones.
4. Probar creación de reportes DOCX/PDF con LibreOffice e inspección visual del documento final.
5. Comprobar privacidad de tablas y datasets, con grupos pequeños y datos exógenos sensibles.
6. Revisión de seguridad de claves, datos anteriores en exports_storage, recuperación y backups.
7. Preparar build estático para producción, servidor HTTPS y observabilidad; no publicar Vite dev.
8. Completar auditoría metodológica de baremos y afirmaciones oficiales antes de comercialización.

## Advertencias y pendientes

- El JWT de administrador sigue usando localStorage; migrar a cookies HttpOnly, CSRF y rotación.
- Deben revisarse controles de acceso a referencias relacionadas dentro de bodies complejos.
- Falta implementar política RLS opcional en PostgreSQL y rate-limiting distribuido.
- El generador QR externo transmite el enlace al proveedor; migrar a QR local.
- La generación PDF requiere LibreOffice instalado, probado y operable por el servicio.
- Las pruebas automatizadas nuevas no equivalen a un ensayo de penetración ni homologación profesional.
