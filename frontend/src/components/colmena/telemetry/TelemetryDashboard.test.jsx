import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import TelemetryDashboard from './TelemetryDashboard.jsx';

vi.mock('./ExecutiveDecisionBoard.jsx', () => ({
  default: ({ technicalControl }) => <div>Executive Decision Board{technicalControl}</div>,
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
    fireEvent.change(screen.getByRole('combobox', { name: 'Herramientas técnicas' }), { target: { value: 'advanced' } });
    expect(screen.getByText('Legacy Advanced Explorer Loaded')).toBeInTheDocument();
    fireEvent.change(screen.getByRole('combobox', { name: 'Herramientas técnicas' }), { target: { value: 'none' } });
    expect(screen.queryByText('Legacy Advanced Explorer Loaded')).not.toBeInTheDocument();
  });
  it('exposes detailed survey evidence only on demand', () => {
    render(<TelemetryDashboard projectId={1} studyId={3} telemetry={{valid_count:20}}
      descriptives={{}} isLoadingTelemetry={false} />);
    fireEvent.change(screen.getByRole('combobox', { name: 'Herramientas técnicas' }), { target: { value: 'questions' } });
    expect(screen.getByText('Questions Detail Loaded')).toBeInTheDocument();
  });
  it('shows saved diagnostic when capture telemetry is unavailable', () => {
    render(<TelemetryDashboard projectId={1} studyId={3} telemetry={null}
      descriptives={null} isLoadingTelemetry={false} />);
    expect(screen.getByText('Executive Decision Board')).toBeInTheDocument();
    expect(screen.queryByText('Sin datos de seguimiento')).not.toBeInTheDocument();
  });

});
