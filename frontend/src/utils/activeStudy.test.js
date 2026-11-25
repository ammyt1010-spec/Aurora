import { beforeEach, describe, expect, it } from 'vitest';

import { getActiveStudyId, setActiveStudyId } from './activeStudy.js';

describe('activeStudy', () => {
  beforeEach(() => localStorage.clear());

  it('recuerda la aplicación por evaluación empresarial', () => {
    setActiveStudyId(101, 31);
    setActiveStudyId(102, 32);
    expect(getActiveStudyId(101)).toBe(31);
    expect(getActiveStudyId(102)).toBe(32);
  });

  it('no inventa una aplicación si todavía no existe', () => {
    expect(getActiveStudyId(101)).toBeNull();
  });
});
