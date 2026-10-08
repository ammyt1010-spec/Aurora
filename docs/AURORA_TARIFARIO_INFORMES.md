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


## Tarifario web propuesto: 20 % inferior al documento de referencia

| Trabajadores | SUSESO/ISTAS21 breve | CENSOPAS corta | CENSOPAS media |
|---|---:|---:|---:|
| 1–100 | S/ 160 | S/ 400 | S/ 560 |
| 101–300 | S/ 240 | S/ 600 | S/ 920 |
| 301–500 | S/ 320 | S/ 720 | S/ 1200 |
| 501–999 | S/ 400 | S/ 1000 | S/ 1560 |
| 1000–1999 | S/ 560 | Cotizar | Cotizar |
| 2000+ | Cotizar | Cotizar | Cotizar |

Base: columnas «Plataforma Web» de las imágenes aportadas por el propietario,
reducidas exactamente al 80 % de los importes de referencia. No se han
tomado las columnas de encuesta en físico.

Los tramos `Cotizar` requieren precio explícito por el operador.
El tarifario se importa una sola vez **mediante acción confirmada del
administrador central**. La migración de datos no sobreescribe precios.

### Extras de la referencia (comparación; no se facturan automáticamente)

- SUSESO, explicación de metodología S/170 → propuesta S/136.
- SUSESO, explicación de resultados S/170 → propuesta S/136.
- CENSOPAS corta, explicación de resultados S/200 → propuesta S/160.
- CENSOPAS media, explicación de resultados S/250 → propuesta S/200.
- Día adicional tras la fecha máxima de respuesta S/15 → referencia
  reducida S/12, **no activada**.
- Uso de plataforma por evaluación abandonada S/100 → referencia
  reducida S/80, **no activada**.

Estos componentes opcionales NO están incluidos en la orden estándar.
Necesitan aprobación comercial específica para incorporarse al sistema.

### Precisión tributaria y metodología

El documento de referencia declara «No incluye IGV». El tratamiento
tributario de las tarifas de AURORA está pendiente de confirmación;
**no afirmamos que los importes sean finales con IGV incluido**.
La existencia de una tarifa no equivale a la autorización, licencia
o validación oficial del cuestionario empleado.
