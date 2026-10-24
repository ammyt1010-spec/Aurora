import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { renderWithQueryClient } from '../test-utils/renderWithQueryClient.jsx';
import { getPublicEvaluationBundle } from '../api/evaluationBundles.js';
import PublicBundlePage from './PublicBundlePage.jsx';

vi.mock('../api/evaluationBundles.js', () => ({ getPublicEvaluationBundle: vi.fn() }));
vi.mock('./PublicSurveyPage.jsx', () => ({
  default: ({ publicIdOverride, batteryContext, onCompleted }) => (
    <section>
      <p>{batteryContext}</p>
      <p>Cuestionario: {publicIdOverride}</p>
      <button type="button" onClick={onCompleted}>Finalizar instrumento</button>
    </section>
  ),
}));
const payload={title:'Batería de prueba',evaluations:[
  {id:11,name:'Psicosocial',instrument_name:'CENSOPAS',survey_public_id:'abc'},
  {id:12,name:'Ergonomía',instrument_name:'ROSA',survey_public_id:'def'},
]};
function renderPage(){
  return renderWithQueryClient(<MemoryRouter initialEntries={['/bateria/test']}>
    <Routes><Route path="/bateria/:publicId" element={<PublicBundlePage/>}/></Routes>
  </MemoryRouter>);
}
beforeEach(()=>{vi.clearAllMocks();getPublicEvaluationBundle.mockResolvedValue(payload)});
describe('Batería AURORA en una sola URL',()=>{
  it('muestra los instrumentos de manera continua sin abrir pestañas',async()=>{
    renderPage();
    expect(await screen.findByText('Cuestionario: abc')).toBeInTheDocument();
    expect(screen.queryByText('Cuestionario: def')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Finalizar instrumento'}));
    expect(await screen.findByText('Cuestionario: def')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Finalizar instrumento'}));
    expect(await screen.findByText('Has completado la batería')).toBeInTheDocument();
    expect(getPublicEvaluationBundle).toHaveBeenCalledTimes(3);
  });
  it('impide continuar si la batería se revocó durante una encuesta',async()=>{
    getPublicEvaluationBundle.mockResolvedValueOnce(payload)
      .mockRejectedValueOnce(new Error('revocado'));
    renderPage();
    expect(await screen.findByText('Cuestionario: abc')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Finalizar instrumento'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('La batería ya no está disponible');
    expect(screen.queryByText('Cuestionario: def')).not.toBeInTheDocument();
  });
});
