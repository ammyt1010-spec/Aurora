import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { getDocument } from 'pdfjs-dist';
import PdfCanvasViewer from './PdfCanvasViewer.jsx';

vi.mock('pdfjs-dist', () => ({
  GlobalWorkerOptions: { workerSrc: '' },
  getDocument: vi.fn(),
}));

describe('visor PDF de Aurora', () => {
  let getPage;

  beforeEach(() => {
    getPage = vi.fn(async () => ({
      getViewport: ({ scale }) => ({ width: 600 * scale, height: 800 * scale }),
      render: () => ({ promise: Promise.resolve(), cancel: vi.fn() }),
    }));
    getDocument.mockReturnValue({
      promise: Promise.resolve({ numPages: 3, getPage }),
      destroy: vi.fn(),
    });
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ({}));
  });

  it('muestra las páginas sin depender del visor integrado del navegador', async () => {
    const blob = { arrayBuffer: async () => new ArrayBuffer(8) };
    render(<PdfCanvasViewer blob={blob} />);

    expect(await screen.findByLabelText('Página 1 de 3 del informe PDF')).toBeInTheDocument();
    await waitFor(() => expect(getPage).toHaveBeenCalledWith(1));
    fireEvent.click(screen.getByRole('button', { name: 'Página siguiente' }));
    expect(await screen.findByLabelText('Página 2 de 3 del informe PDF')).toBeInTheDocument();
    await waitFor(() => expect(getPage).toHaveBeenCalledWith(2));
    fireEvent.change(screen.getByRole('combobox', { name: 'Página del informe' }), { target: { value: '3' } });
    await waitFor(() => expect(getPage).toHaveBeenCalledWith(3));
  });
});
