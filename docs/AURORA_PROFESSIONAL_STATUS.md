# AURORA Professional: Implementación y criterios de lanzamiento

**Estado:** mejoras integradas en `hardening/aurora-professional-v1`.
**Rama principal:** sin fusionar. Revisar el PR #1 y GitHub Actions antes de desplegar.

## Implementado en código

1. API privada protegida con JWT y autorizaciones por proyecto, estudio y objeto.
2. Validación de las referencias de otros recursos enviadas en los JSON,
   con pruebas reales de aislamiento multiempresa.
3. Sesiones navegador mediante cookies HttpOnly, SameSite Strict y CSRF;
   Bearer JWT sigue disponible para herramientas API.
4. Límite de solicitudes compartido en PostgreSQL: formularios públicos,
   autenticación y registro. Claves IP se guardan como HMAC, no como texto plano.
5. Invitaciones personales de un solo uso y tokens separados por sesión
   para encuestas anónimas; sin vínculo persistente invitación-respuesta.
6. Gestión de equipos: propietario, administrador, editor y lector;
   interfaz de colaboración e invitación por correo registrado.
7. Exportaciones protegidas, registro de descargas y redacción de rutas
   internas del servidor en respuestas HTTP.
8. CSV, XLSX y JSON más paquete ZIP de importación Power BI (CSV con
   diccionario). Textos peligrosos se neutralizan al exportar hojas.
9. Vista previa autenticada de reportes Word/PDF y error explícito si
   LibreOffice no puede producir un PDF fiel.
10. Código QR generado en el navegador sin enviar enlaces de encuestas
    a servidores de generación de imágenes externos.
11. Corrección de la interpretación de valores históricos en escalas 0..100,
    casos de cálculo de referencia, advertencia de omega aproximada por PCA.
12. Base de datos: migraciones 0015/0016, índices para estudios grandes
    y prueba de upgrade real PostgreSQL 16 en GitHub Actions.
13. Operación: endpoint readiness de base de datos, respaldos pg_dump
    verificables, proxy para assets compilados y documentación de restauración.
14. Pipeline CI: npm ci sobre lockfile persistido, build, Vitest,
    Pytest + pruebas de controles de acceso + migraciones PostgreSQL.

## Requisitos aún pendientes de aprobación/validación

- **Seguridad:** realizar pentest profesional autenticado y anónimo,
  penetración multiempresa, autorización de referencias complejas y RLS
  opcional. Completar rotación/revocación server-side de sesiones.
- **Privacidad:** clasificar y revisar todos los archivos ya incluidos en
  el historial de Git; diseñar su saneamiento coordinado con el propietario,
  implementar retención y respuesta a solicitudes de los titulares.
- **Metodología:** verificar los baremos del instrumento contra fuentes
  autorizadas y contrastar resultados contra un motor independiente;
  evaluar omega factorial en vez de equiparar PCA a CFA.
- **Documentos:** realizar inspección visual de PDF/DOCX reales y pruebas
  de firmas, tablas, gráficos y redacción final por especialistas.
- **Operación:** restaurar respaldo en entorno aislado y ejecutar carga
  sintética y concurrencia de cientos/miles de encuestas.
- **Integraciones:** SPSS nativo .sav y Parquet requieren motores específicos
  y pruebas de interoperabilidad. El ZIP Power BI no es un archivo PBIX.
- **Comercial:** verificar condiciones regulatorias y evitar presentar una
  ficha o reporte como avalado por SUNAFIL sin evidencia documental.

## Criterios para permitir fusionar a main

- Todos los jobs del último commit están en verde.
- Auditoría de diferencias aprobada por el responsable técnico.
- Instalación y migración reproducibles con backup y rollback probado.
- Aislamiento probado con usuarios de 2 organizaciones diferentes.
- Validación metodológica firmada por el profesional responsable.
- Revisión visual de un PDF y DOCX con datos sintéticos.
- Aprobación expresa para activar un entorno con datos reales.

**No equivale a software certificado ni a disponibilidad comercial.**
