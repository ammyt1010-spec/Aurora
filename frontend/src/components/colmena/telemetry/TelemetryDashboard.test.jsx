import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import TelemetryDashboard from './TelemetryDashboard.jsx';

vi.mock('./ExecutiveDecisionBoard.jsx', () => ({
  default: () => <div>Executive Decision Board</div>,
}));
vi.mock('./PremiumBIWorkspace.jsx', () => ({
  default: () => <div>Legacy Advanced Explorer Loaded</div>,
}));
vi.mock('./TelemetryOverview.jsx', () => ({
  default: () => <div>Full Capture Telemetry Loaded</div>,
}));
vi.mock('./TelemetryDimensionsSection.jsx', () => ({
  default: () => <div>Questions Detail Loaded</div>,
}));

describe('Compact telemetry default', () => {
  it('mounts only executive board until technical view is requested', () => {
    render(<TelemetryDashboard projectId={1} organizationId={2} studyId={3}
      telemetry={{valid_count:20}} descriptives={{}} isLoadingTelemetry={false} />);
    expect(screen.getByText('Executive Decision Board')).toBeInTheDocument();
    expect(screen.queryByText('Legacy Advanced Explorer Loaded')).not.toBeInTheDocument();
    expect(screen.queryByText('Full Capture Telemetry Loaded')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:/Explorador avanzado/}));
    expect(screen.getByText('Legacy Advanced Explorer Loaded')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:/Explorador avanzado/}));
    expect(screen.queryByText('Legacy Advanced Explorer Loaded')).not.toBeInTheDocument();
  });
  it('exposes detailed survey evidence only on demand', () => {
    render(<TelemetryDashboard projectId={1} studyId={3} telemetry={{valid_count:20}}
      descriptives={{}} isLoadingTelemetry={false} />);
    fireEvent.click(screen.getByRole('button',{name:/Evidencia por pregunta/}));
    expect(screen.getByText('Questions Detail Loaded')).toBeInTheDocument();
  });
});
