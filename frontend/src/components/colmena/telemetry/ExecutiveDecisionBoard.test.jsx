import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { renderWithQueryClient } from '../../../test-utils/renderWithQueryClient.jsx';
import ExecutiveDecisionBoard from './ExecutiveDecisionBoard.jsx';
import { getCensopasReadiness } from '../../../api/instruments.js';
import { getExecutiveDashboard } from '../../../api/reports.js';
import { getCensopasResults, getCensopasUnitResults, getResultsOverview, getStudy, listStudyUnitTypes } from '../../../api/studies.js';

vi.mock('./LongitudinalBIWidget.jsx', () => ({ default: () => <div>Longitudinal view loaded</div> }));
vi.mock('../../../api/instruments.js', () => ({ getCensopasReadiness: vi.fn() }));
vi.mock('../../../api/reports.js', () => ({ getExecutiveDashboard: vi.fn() }));
vi.mock('../../../api/studies.js', () => ({
  getCensopasResults: vi.fn(), getCensopasUnitResults: vi.fn(), getResultsOverview: vi.fn(),
  getStudy: vi.fn(), listStudyUnitTypes: vi.fn(),
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
    projectId={8} studyId={19} telemetry={{valid_count:80}}/></MemoryRouter>);
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
  listStudyUnitTypes.mockResolvedValue([{id:3,name:'Áreas'}]);
  getCensopasUnitResults.mockResolvedValue({results:[
    {...dimension,unit_id:20,unit_name:'Operaciones',unfavorable_pct:60,intermediate_pct:20,favorable_pct:20},
    {...hidden,unit_id:22,unit_name:'Equipo confidencial'},
  ]});
});

describe('AURORA single-screen executive canvas',()=>{
  it('unifies management diagnosis and excludes private rows',async()=>{
    renderBoard();
    expect(await screen.findByRole('heading',{name:'Dimensiones y comparaciones'})).toBeInTheDocument();
    expect(screen.getByRole('heading',{name:'Qué significa'})).toBeInTheDocument();
    expect(screen.getByText('Evaluar distribución de cargas')).toBeInTheDocument();
    expect(screen.queryByText('Privado')).not.toBeInTheDocument();
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText('80')).toBeInTheDocument();
    expect(screen.getByText('Riesgo alto')).toBeInTheDocument();
  });
  it('filters authorized segments without exposing suppressed units',async()=>{
    renderBoard();
    expect(await screen.findByRole('heading',{name:'Diagnóstico ejecutivo'})).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Tipo de segmento'),{target:{value:'3'}});
    expect(await screen.findByRole('columnheader',{name:'Operaciones'})).toBeInTheDocument();
    expect(screen.queryByText('Equipo confidencial')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Unidad del segmento'),{target:{value:'20'}});
    expect(screen.getByText('Comparación descriptiva por segmento')).toBeInTheDocument();
    expect(screen.queryByText('Evaluar distribución de cargas')).not.toBeInTheDocument();
    expect(screen.getAllByText('60.0%').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button',{name:'Restablecer'}));
    expect(screen.getByLabelText('Tipo de segmento').value).toBe('');
  });
  it('keeps generic scores distinct from CENSOPAS categories',async()=>{
    getCensopasReadiness.mockResolvedValue({is_censopas_instrument:false});
    getResultsOverview.mockResolvedValue({results:[
      {construct_code:'Q1',construct_name:'Clima',construct_type:'DIMENSION',
        suppressed:false,mean_score:72},
    ]});
    renderBoard();
    expect(await screen.findByText('Puntuación descriptiva normalizada, no nivel de riesgo')).toBeInTheDocument();
    expect(screen.queryByText('Riesgo alto')).not.toBeInTheDocument();
  });
  it('switches analyses in place without adding vertically stacked dashboards',async()=>{
    renderBoard();
    await screen.findByRole('heading',{name:'Dimensiones y comparaciones'});
    expect(screen.queryByText('Longitudinal view loaded')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Evolución'}));
    expect(screen.getByText('Longitudinal view loaded')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Diagnóstico'}));
    expect(screen.queryByText('Longitudinal view loaded')).not.toBeInTheDocument();
  });

});
