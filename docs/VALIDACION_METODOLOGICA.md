# AURORA: protocolo de validación psicométrica

Esta rama incorpora pruebas de consistencia **algebraica** sobre alfa de
Cronbach, orientación de ítems, promedios ponderados, interpretación de
mapas históricos de 0..100 y criterios mínimos de normalidad.

**No constituyen certificación de equivalencia oficial CENSOPAS-COPSOQ**.

## Requisitos antes de informes definitivos
1. Identificar la versión exacta del instrumento y su licencia de uso.
2. Congelar y documentar el texto de cada ítem, opciones, código fuente,
   pesos, dirección y tratamiento de respuestas faltantes.
3. Aportar baremos verificables, población normativa, fechas, procedencia y
   autorización para describir resultados como oficiales.
4. Comparar los mismos microdatos sintéticos, punto por punto, con una
   implementación independiente de referencia (R/SPSS u otro motor validado).
5. Validar consistencia interna y analizar supuestos de factor único antes
   de interpretar omega. **La omega actual usa PCA unifactorial aproximada,
   no un análisis factorial confirmatorio (CFA)**.
6. Verificar tamaños mínimos de grupos, sensibilidad a datos faltantes y
   que ninguna salida reidentifique a encuestados.
7. Conservar identificador, fecha, hash, versión del algoritmo y autor de
   toda corrida utilizada en un reporte.
8. Emitir una ficha de validación metodológica firmada por el profesional
   responsable, sin atribuir aval SUNAFIL por el solo uso del software.

No habilitar la afirmación "oficial" cuando falta evidencia trazable.
