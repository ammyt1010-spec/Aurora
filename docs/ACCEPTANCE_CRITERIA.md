# Pruebas de aceptación profesional de AURORA

## 1. Confiabilidad funcional
- Crear dos empresas independientes y al menos 3 roles (propietario,
  editor, lector).
- El lector no modifica estudios; un tercero no consulta expedientes
  ajenos; todas las referencias cruzadas rechazan IDs externos.
- Abrir un estudio, consumir dos códigos de invitación, impedir el reuso,
  completar el cuestionario y verificar el scoring.

## 2. Metodología
- Contrastar cada una de las dimensiones con un conjunto independiente
  de resultados aceptados por un metodólogo competente.
- Revisar alfa, omega (método PCA aproximado), normalidad, Mann-Whitney,
  Kruskal-Wallis, Spearman, chi-cuadrado y gestión de datos faltantes.
- Verificar que el reporte no afirme un respaldo oficial que no existe.

## 3. Escalabilidad
- Ejecutar pruebas sintéticas con 100, 500 y 1000 encuestados concurrentes,
  desde fuera del servidor, midiendo p50/p95/p99, tasa de errores y CPU/RAM.
- Comparar tiempos de importación, scoring, exportaciones y DOCX/PDF para
  estudios de 1k, 10k y 50k respuestas.
- Registrar plan `EXPLAIN ANALYZE`, métricas de bloqueo y capacidad
  del hardware de destino antes de comprometer SLAs.

## 4. Recuperación, privacidad y usuarios
- Restauración aislada de PostgreSQL desde el respaldo personalizado.
- Recuperación cifrada de los archivos externos reports_storage y exports_storage.
- Verificar límites de publicación al analizar grupos pequeños.
- Revisar expedientes y exports históricos antes de sanear el historial Git.
- Validar acceso desde Windows, Linux, Android e iOS mediante navegador
  soportado. No se ha construido una aplicación Windows .exe nativa.

**Aprobación requerida por responsables de seguridad, metodología y operación.**
