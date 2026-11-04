import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { renderWithQueryClient } from '../../../test-utils/renderWithQueryClient.jsx';
import ExecutiveDecisionBoard from './ExecutiveDecisionBoard.jsx';
import { getCensopasReadiness } from '../../../api/instruments.js';
import { getExecutiveDashboard } from '../../../api/reports.js';
import { getCensopasAreaResults, getCensopasResults, getCensopasSexResults, getResultsOverview, getStudy } from '../../../api/studies.js';

vi.mock('../../../api/instruments.js', () => ({ getCensopasReadiness: vi.fn() }));
vi.mock('../../../api/reports.js', () => ({ getExecutiveDashboard: vi.fn() }));
vi.mock('../../../api/studies.js', () => ({
  getCensopasAreaResults: vi.fn(), getCensopasResults: vi.fn(), getCensopasSexResults: vi.fn(), getResultsOverview: vi.fn(),
  getStudy: vi.fn(),
}));

const dimension = {
  construct_code:'D1', construct_name:'Carga laboral', construct_type:'DIMENSION', n_valid:80,
  suppressed:false, favorable_pct:20,intermediate_pct:30,unfavorable_pct:50,
  collective_classification:'RIESGO_ALTO', priority_rank:1,
};
const hidden = {...dimension, construct_code:'D2',construct_name:'Privado',suppressed:true,
  favorable_pct:null,intermediate_pct:null,unfavorable_pct:null};

function renderBoard() {
  return renderWithQueryClient(<MemoryRouter><ExecutiveDecisionBoard
    projectId={8} studyId={19} telemetry={{valid_count:80, completed_count:82,
      instrument_name:'CENSOPAS-COPSOQ', instrument_version_code:'SHORT-OFICIAL'}}/></MemoryRouter>);
}
beforeEach(()=>{
  vi.clearAllMocks();
  getStudy.mockResolvedValue({id:19, instrument_version_id:7});
  getCensopasReadiness.mockResolvedValue({is_censopas_instrument:true});
  getCensopasResults.mockResolvedValue({results:[dimension,hidden]});
  getResultsOverview.mockResolvedValue({results:[]});
  getExecutiveDashboard.mockResolvedValue({
    construct_rankings:[{construct_code:'D1',recommendation:'Evaluar distribución de cargas'}],
    risk_distribution:{high_risk_count:1}, participation:{valid_count:80},
  });
  getCensopasAreaResults.mockResolvedValue({available:true,results:[
    {...dimension,group_value:'Operaciones',unfavorable_pct:60,intermediate_pct:20,favorable_pct:20},
    {...hidden,group_value:'Equipo confidencial'},
  ]});
  getCensopasSexResults.mockResolvedValue({available:true,results:[
    {...dimension,group_value:'Mujer',n_valid:40,unfavorable_pct:70,intermediate_pct:20,favorable_pct:10},
    {...dimension,group_value:'Hombre',n_valid:40,unfavorable_pct:30,intermediate_pct:40,favorable_pct:30},
  ]});
});

describe('AURORA liquid telemetry',()=>{
  it('shows the actual instrument, dimensions and publishable evidence',async()=>{
    renderBoard();
    expect(await screen.findByRole('heading',{name:'Dimensiones del instrumento'})).toBeInTheDocument();
    expect(screen.getByRole('heading',{name:'CENSOPAS-COPSOQ'})).toBeInTheDocument();
    expect(screen.getByText(/20.0% favorable · 30.0% intermedio/)).toBeInTheDocument();
    expect(screen.queryByText('Privado')).not.toBeInTheDocument();
    expect(screen.getByText('80')).toBeInTheDocument();
    expect(screen.getByText('Riesgo alto')).toBeInTheDocument();
    expect(screen.getByText('Enlace abierto · sin denominador de invitación')).toBeInTheDocument();
    expect(screen.queryByText('89%')).not.toBeInTheDocument();
  });
  it('filters authorized segments without exposing suppressed units',async()=>{
    renderBoard();
    expect(await screen.findByRole('heading',{name:'Dimensiones del instrumento'})).toBeInTheDocument();
    expect(await screen.findByRole('option',{name:'Operaciones'})).toBeInTheDocument();
    expect(screen.queryByText('Equipo confidencial')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Filtrar por área'),{target:{value:'Operaciones'}});
    expect(screen.queryByText('Evaluar distribución de cargas')).not.toBeInTheDocument();
    expect(screen.getAllByText('60.0%').length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText('Filtrar por sexo'),{target:{value:'Mujer'}});
    expect(screen.getByLabelText('Filtrar por área').value).toBe('ALL');
    expect(screen.getAllByText('70.0%').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button',{name:/Toda la empresa/}));
    expect(screen.getByLabelText('Filtrar por sexo').value).toBe('ALL');
  });
  it('keeps generic scores distinct from CENSOPAS categories',async()=>{
    getCensopasReadiness.mockResolvedValue({is_censopas_instrument:false});
    getResultsOverview.mockResolvedValue({results:[
      {construct_code:'Q1',construct_name:'Clima',construct_type:'DIMENSION',
        suppressed:false,mean_score:72},
    ]});
    renderBoard();
    expect(await screen.findByText('Puntajes descriptivos normalizados; no equivalen a nivel de riesgo.')).toBeInTheDocument();
    expect(screen.queryByText('Riesgo alto')).not.toBeInTheDocument();
  });
  it('keeps the invitation denominator attached to the valid response count',async()=>{
    renderWithQueryClient(<MemoryRouter><ExecutiveDecisionBoard projectId={8} studyId={19}
      telemetry={{valid_count:80, invited_count:100, completed_count:82}}/></MemoryRouter>);
    expect(await screen.findByText('de 100 convocados')).toBeInTheDocument();
    expect(screen.queryByText('80.0%')).not.toBeInTheDocument();
  });

  it('shows a real error instead of endless loading when study fails',async()=>{
    getStudy.mockRejectedValue(new Error('Falló conexión'));
    renderBoard();
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo consultar el diagnóstico metodológico');
  });

});
