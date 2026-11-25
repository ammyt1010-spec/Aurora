const dimensions = [
  { label: 'Exigencias psicológicas', favorable: 28, intermediate: 42, unfavorable: 30 },
  { label: 'Doble presencia', favorable: 34, intermediate: 38, unfavorable: 28 },
  { label: 'Recompensas', favorable: 48, intermediate: 33, unfavorable: 19 },
  { label: 'Apoyo social', favorable: 58, intermediate: 27, unfavorable: 15 },
];

export default function AuroraProductPreview({ compact = false }) {
  return (
    <div className={`aurora-preview${compact ? ' aurora-preview--compact' : ''}`} role="group" aria-label="Vista ilustrativa del tablero AURORA con indicadores y riesgos por dimensión">
      <div className="aurora-preview__top">
        <div className="aurora-preview__top-left">
          <span className="aurora-preview__mark" aria-hidden="true"><span /><span /><span /></span>
          <div>
            <strong>Centro de decisiones</strong>
            <small>CENSOPAS-COPSOQ · Resumen</small>
          </div>
        </div>
        <span className="aurora-preview__status"><i /> Vista de producto</span>
      </div>

      <div className="aurora-preview__filters" aria-hidden="true">
        <span>Empresa: todas</span><span>Área: todas</span><span>Sexo: todos</span>
      </div>

      <div className="aurora-preview__metrics">
        <div className="aurora-preview__metric"><span>Respuestas válidas</span><strong>112</strong><small>Participación recibida</small></div>
        <div className="aurora-preview__metric"><span>Cobertura</span><strong>89<span>%</span></strong><small>De la población invitada</small></div>
        <div className="aurora-preview__metric aurora-preview__metric--accent"><span>Focos a revisar</span><strong>03</strong><small>Dimensiones prioritarias</small></div>
      </div>

      <div className="aurora-preview__analysis">
        <div className="aurora-preview__chart">
          <div className="aurora-preview__section-head">
            <div><strong>Lectura por dimensión</strong><span>Distribución de resultados</span></div>
            <span className="aurora-preview__mini-pill">% de respuestas</span>
          </div>
          <div className="aurora-preview__rows" role="img" aria-label="Exigencias psicológicas 30% desfavorable; doble presencia 28%; recompensas 19%; apoyo social 15%. Datos ilustrativos.">
            {dimensions.map((dimension) => (
              <div className="aurora-preview__row" key={dimension.label}>
                <span>{dimension.label}</span>
                <div className="aurora-preview__bar" aria-hidden="true">
                  <i className="aurora-preview__bar--good" style={{ width: `${dimension.favorable}%` }} />
                  <i className="aurora-preview__bar--mid" style={{ width: `${dimension.intermediate}%` }} />
                  <i className="aurora-preview__bar--risk" style={{ width: `${dimension.unfavorable}%` }} />
                </div>
                <b>{dimension.unfavorable}%</b>
              </div>
            ))}
          </div>
          <div className="aurora-preview__legend"><span><i className="good" /> Favorable</span><span><i className="mid" /> Intermedio</span><span><i className="risk" /> Desfavorable</span></div>
        </div>
        <div className="aurora-preview__insight">
          <div className="aurora-preview__section-head"><div><strong>Foco principal</strong><span>Prioridad de revisión</span></div></div>
          <div className="aurora-preview__dial" aria-hidden="true"><div><strong>30%</strong><span>desfavorable</span></div></div>
          <strong className="aurora-preview__insight-label">Exigencias psicológicas</strong>
          <p>Una señal clara para profundizar por área y orientar las acciones del equipo.</p>
        </div>
      </div>
      <div className="aurora-preview__foot"><span><i /> Análisis por áreas, sedes y grupos</span><span>Datos ilustrativos</span></div>
    </div>
  );
}
