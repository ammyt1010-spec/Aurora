import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import ThemeToggle from './ThemeToggle.jsx';

describe('AURORA theme preference', () => {
  afterEach(() => {
    document.documentElement.classList.remove('dark');
    localStorage.removeItem('aurora-theme');
    vi.unstubAllGlobals();
  });

  it('respects the saved light choice even when the system prefers dark', () => {
    localStorage.setItem('aurora-theme', 'light');
    vi.stubGlobal('matchMedia', () => ({ matches: true }));
    render(<ThemeToggle />);

    expect(document.documentElement).not.toHaveClass('dark');
    fireEvent.click(screen.getByRole('button', { name: 'Alternar tema oscuro' }));
    expect(document.documentElement).toHaveClass('dark');
    expect(localStorage.getItem('aurora-theme')).toBe('dark');
  });

  it('restores a saved dark choice and can return to light', () => {
    localStorage.setItem('aurora-theme', 'dark');
    vi.stubGlobal('matchMedia', () => ({ matches: false }));
    render(<ThemeToggle />);

    expect(document.documentElement).toHaveClass('dark');
    fireEvent.click(screen.getByRole('button', { name: 'Alternar tema oscuro' }));
    expect(document.documentElement).not.toHaveClass('dark');
    expect(localStorage.getItem('aurora-theme')).toBe('light');
  });
});
