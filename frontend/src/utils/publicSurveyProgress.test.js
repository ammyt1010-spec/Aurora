import { beforeEach, expect, it } from 'vitest';
import { readProgress, writeProgress } from './publicSurveyProgress.js';
beforeEach(() => sessionStorage.clear());
it('purges expired credentials and answers and keeps an explicit restart marker', () => {
  sessionStorage.setItem(
    'survey',
    JSON.stringify({
      session: { access_token: 'secret' },
      answers: { 1: 'private' },
      savedAt: Date.now() - 13 * 60 * 60 * 1000,
    }),
  );
  expect(readProgress('survey').expired).toBe(true);
  expect(sessionStorage.getItem('survey')).not.toContain('secret');
  expect(sessionStorage.getItem('survey')).not.toContain('private');
  expect(readProgress('survey').expired).toBe(true);
});
it('retains a completion marker for the tab lifetime without credentials', () => {
  writeProgress('survey', { completed: true });
  expect(readProgress('survey').completed).toBe(true);
});

it('keeps the non-sensitive battery position while individual survey drafts expire', () => {
  sessionStorage.setItem(
    'battery',
    JSON.stringify({
      currentIndex: 2,
      studies: ['a', 'b', 'c'],
      savedAt: Date.now() - 13 * 60 * 60 * 1000,
    }),
  );
  expect(readProgress('battery', { expires: false }).currentIndex).toBe(2);
});
