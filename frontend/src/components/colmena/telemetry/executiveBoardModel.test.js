import { describe, expect, it } from 'vitest';
import { actionForDimension, comparisonUnits, executiveRows, matrixCells, maxUnfavorable, riskLabel, selectedDimension } from './executiveBoardModel.js';

const base = { construct_type:'DIMENSION', construct_code:'D1', construct_name:'Carga', n_valid:23,
  favorable_pct:20, intermediate_pct:30, unfavorable_pct:50, priority_rank:1, collective_classification:'RIESGO_ALTO' };

describe('Executive one screen model', () => {
  it('suppresses private and incomplete classifications', () => {
    const input=[base,{...base,construct_code:'D2',suppressed:true},
      {...base,construct_code:'D3', intermediate_pct:null},{...base,construct_code:'D4',unfavorable_pct:200}];
    expect(executiveRows(input,true).map(x=>x.construct_code)).toEqual(['D1']);
  });
  it('does not mislabel generic scores as CENSOPAS risk',()=>{
    expect(executiveRows([{...base,mean_score:60,favorable_pct:null}],false)).toHaveLength(1);
    expect(executiveRows([{...base,mean_score:60,favorable_pct:null}],true)).toHaveLength(0);
  });
  it('returns only public units and cells', () => {
    const input=[{...base,unit_id:8,unit_name:'Planta'},
      {...base,unit_id:9,unit_name:'Privado',suppressed:true}];
    expect(comparisonUnits(input)).toEqual([{id:'8',label:'Planta'}]);
    expect(matrixCells(input).get('D1::9')).toBeUndefined();
    expect(matrixCells(input).get('D1::8').unfavorable_pct).toBe(50);
  });
  it('maintains server classification and recommendation',()=>{
    expect(riskLabel('RIESGO_ALTO')).toBe('Riesgo alto');
    expect(maxUnfavorable([base])).toBe(50);
    expect(selectedDimension([base], 'missing').construct_code).toBe('D1');
    expect(actionForDimension([{construct_code:'D1',recommendation:'Revisar turnos'}], 'D1').recommendation).toBe('Revisar turnos');
  });
});
