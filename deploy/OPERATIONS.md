# AURORA: operación segura y recuperación

## Respaldo y restauración

- Configura almacenamiento **cifrado**, separado del servidor, con permisos
  restringidos. No almacenes respaldos dentro del repositorio Git.
- Establece `PGHOST`, `PGPORT`, `PGUSER`, `PGDATABASE` y credenciales por
  archivo seguro `.pgpass` o gestor de secretos. No imprimas secretos en los logs.
- Ejecuta `AURORA_BACKUP_DIR=/ruta/cifrada deploy/backup_postgres.sh`
  mediante programación del sistema. Mantén versiones históricas según
  política de retención legal y contrato del cliente.
- Prueba una restauración **en base aislada** con
  `pg_restore --no-owner --no-acl --dbname=aurora_restore ARCHIVO.dump`.
  No sobrescribas producción sin un procedimiento aprobado.
- Respalda también `exports_storage` y `reports_storage` en un volumen
  cifrado, porque los archivos de los informes no viven en la base de datos.
- Para examinar el servicio: `GET /health` es liveness;
  `GET /health/ready` requiere una conexión real a la BD.

## Riesgos aún sujetos a aceptación profesional

La verificación de migraciones en PostgreSQL no sustituye ensayos de
restauración, autorización multiempresa, calidad psicométrica y carga con datos
reales anonimizados. El borrado irreversible debe tener procedimiento y
autorización del responsable de protección de datos.
