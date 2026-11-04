import { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut } from 'lucide-react';
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist';
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

export default function PdfCanvasViewer({ blob, onError }) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const [document, setDocument] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [pageCount, setPageCount] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [containerWidth, setContainerWidth] = useState(820);
  const [loading, setLoading] = useState(Boolean(blob));
  const [rendering, setRendering] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!blob) {
      setDocument(null);
      setPageCount(0);
      setLoading(false);
      return undefined;
    }
    let cancelled = false;
    let task;
    setLoading(true);
    setError('');
    setPageNumber(1);
    setDocument(null);
    blob.arrayBuffer().then((buffer) => {
      if (cancelled) return;
      task = getDocument({ data: new Uint8Array(buffer) });
      return task.promise;
    }).then((pdf) => {
      if (!pdf || cancelled) return;
      setDocument(pdf);
      setPageCount(pdf.numPages);
      setLoading(false);
    }).catch((cause) => {
      if (cancelled) return;
      setError('No se pudo abrir el PDF en el visor. Puedes descargar el archivo para revisarlo.');
      setLoading(false);
      onError?.(cause);
    });
    return () => {
      cancelled = true;
      task?.destroy();
    };
  }, [blob, onError]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element || typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(([entry]) => {
      setContainerWidth(Math.max(320, entry.contentRect.width - 32));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!document || !canvasRef.current) return undefined;
    let cancelled = false;
    let renderTask;
    setRendering(true);
    document.getPage(pageNumber).then((page) => {
      if (cancelled) return;
      const canvas = canvasRef.current;
      if (!canvas) return;
      const base = page.getViewport({ scale: 1 });
      const width = Math.min(containerWidth, 980) * zoom;
      const viewport = page.getViewport({ scale: width / base.width });
      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(viewport.width * pixelRatio);
      canvas.height = Math.floor(viewport.height * pixelRatio);
      canvas.style.width = `${Math.floor(viewport.width)}px`;
      canvas.style.height = `${Math.floor(viewport.height)}px`;
      renderTask = page.render({
        canvasContext: canvas.getContext('2d'),
        viewport,
        transform: pixelRatio === 1 ? null : [pixelRatio, 0, 0, pixelRatio, 0, 0],
      });
      return renderTask.promise;
    }).then(() => {
      if (!cancelled) setRendering(false);
    }).catch((cause) => {
      if (cancelled || cause?.name === 'RenderingCancelledException') return;
      setRendering(false);
      setError('No se pudo dibujar esta página. Descarga el PDF para revisarla.');
      onError?.(cause);
    });
    return () => {
      cancelled = true;
      renderTask?.cancel();
    };
  }, [document, pageNumber, containerWidth, zoom, onError]);

  return <div className="aurora-pdf-reader" ref={containerRef}>
    <div className="aurora-pdf-toolbar">
      <div className="aurora-pdf-toolbar-group">
        <button type="button" aria-label="Página anterior" disabled={pageNumber <= 1 || loading} onClick={() => setPageNumber((value) => value - 1)}><ChevronLeft size={16} /></button>
        <label className="aurora-pdf-page-label">Página
          <select aria-label="Página del informe" value={pageNumber} disabled={!pageCount} onChange={(event) => setPageNumber(Number(event.target.value))}>
            {Array.from({ length: pageCount }, (_, index) => <option key={index + 1} value={index + 1}>{index + 1}</option>)}
          </select>
          <span>de {pageCount || '—'}</span>
        </label>
        <button type="button" aria-label="Página siguiente" disabled={pageNumber >= pageCount || loading} onClick={() => setPageNumber((value) => value + 1)}><ChevronRight size={16} /></button>
      </div>
      <div className="aurora-pdf-toolbar-group">
        <button type="button" aria-label="Reducir zoom" disabled={zoom <= 0.75} onClick={() => setZoom((value) => Math.max(0.75, Number((value - 0.25).toFixed(2))))}><ZoomOut size={16} /></button>
        <span className="aurora-pdf-zoom">{Math.round(zoom * 100)}%</span>
        <button type="button" aria-label="Aumentar zoom" disabled={zoom >= 1.5} onClick={() => setZoom((value) => Math.min(1.5, Number((value + 0.25).toFixed(2))))}><ZoomIn size={16} /></button>
      </div>
    </div>
    <div className="aurora-pdf-stage" aria-busy={loading || rendering}>
      {loading && <p role="status">Abriendo el informe…</p>}
      {error && <p role="alert" className="aurora-pdf-error">{error}</p>}
      {document && <canvas ref={canvasRef} aria-label={`Página ${pageNumber} de ${pageCount} del informe PDF`} />}
    </div>
  </div>;
}
