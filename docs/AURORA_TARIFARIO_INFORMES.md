# AURORA Professional: monetización y ciclo de emisión

## Decisión del propietario (8 octubre de 2026)

- Plataforma **web privada centralizada**, multidisciplinaria y de acceso
  empresarial con administrador.
- **No hay licencias anuales ni suscripciones** para generar informes.
- Cada informe nuevo solicitado por una empresa requiere una autorización
  de pago distinta.
- El importe se determina por un **tramo editable de cantidad de trabajadores**.
  La moneda inicial es **PEN**.
- El dueño de AURORA definirá próximamente los importes; se prohíbe inventar
  o preinstalar precios.
- Las tarifas solamente pueden ser modificadas por el **operador central**,
  configurado en `BILLING_OPERATOR_USER_ID`, no por el cliente.
- La cotización tiene una vigencia de siete días y guarda una fotografía
  inmutable del tramo, precio, trabajadores y moneda.
- El administrador empresarial solicita cotización; el operador central
  confirma pago manualmente **después** de revisar una fuente independiente.
- La emisión de un informe consume una orden pagada. Volver a descargar el
  mismo documento no genera otro cobro.
- La generación de nuevos informes, con sus propios resultados y fecha,
  corresponde a nuevas cotizaciones.
- Se puede crear y gestionar estudios antes de pagar, pero en producción
  **no se puede emitir un informe final sin una orden pagada**.

## Estados comerciales

`PENDING_PAYMENT` → `PAID` → `CONSUMED`

Las cotizaciones vencidas se rechazan al momento de confirmar. La emisión
de un informe no incrementa el precio según el número real de respuestas:
el precio se fija al cotizar con el número de trabajadores declarado.

## Configuración y precauciones

- Establecer `BILLING_OPERATOR_USER_ID` tras la creación segura de la
  cuenta propietaria del sistema. Sin ese ID no hay gestión de pagos o
  tarifarios. **Nunca** dar credenciales del operador central a clientes.
- No hay pasarela bancaria automatizada: la referencia de pago es un
  comprobante administrativo, no verificación automática del banco.
- La versión de desarrollo permite pruebas heredadas de reportes sin
  cobro. El modo producción exige orden pagada.
- La monetización no sustituye permisos de estudio, control documental,
  declaración fiscal ni auditoría. Cada empresa es responsable de
  declarar el número verdadero de trabajadores.
- Las cotizaciones antiguas se mantienen aunque cambie el tarifario.
- Si cambia la política de cobro (precio por trabajador en lugar de por
  tramo), crear una nueva versión del cálculo sin reescribir el historial.

## Mejoras pendientes para salir a producción

Confirmar por escrito los tramos y montos, definir registro fiscal,
conciliación bancaria, tratamiento de reembolsos y cancelación, impuestos,
comprobantes electrónicos, antifraude y responsabilidades del operador.
La autorización por pago debe validarse bajo concurrencia PostgreSQL.
