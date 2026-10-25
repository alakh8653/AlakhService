import { render, screen } from '@testing-library/react';
import SystemHealthPage from '../SystemHealthPage';
import ServiceMetricsPage from '../ServiceMetricsPage';
import { getServiceMetrics, getSystemHealth, type ServiceMetric } from '../MonitoringService';

vi.mock('../MonitoringService', () => ({ getSystemHealth: vi.fn(), getServiceMetrics: vi.fn() }));

const checkedAt = new Date().toISOString();

describe('SystemHealthPage', () => {
  it('summarises health and lists failing services first', async () => {
    vi.mocked(getSystemHealth).mockResolvedValue([
      { id: 'a', name: 'auth_service', status: 'healthy', checkedAt },
      { id: 'p', name: 'payment_service', status: 'down', checkedAt },
    ]);
    render(<SystemHealthPage />);
    expect(await screen.findByText('1 of 2 services need attention: payment_service')).toBeInTheDocument();
    const names = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    expect(names).toEqual(['payment_service', 'auth_service']);
  });

  it('says when everything is healthy', async () => {
    vi.mocked(getSystemHealth).mockResolvedValue([{ id: 'a', name: 'auth_service', status: 'healthy', checkedAt }]);
    render(<SystemHealthPage />);
    expect(await screen.findByText('All 1 services are healthy.')).toBeInTheDocument();
  });
});

describe('ServiceMetricsPage', () => {
  const metric = (service: string, over: Partial<ServiceMetric> = {}): ServiceMetric => ({
    id: service,
    service,
    requests: 1200,
    requestsPerMinute: 240,
    errorRate: 0,
    p50LatencyMs: 10,
    p95LatencyMs: 40,
    circuit: 'closed',
    ...over,
  });

  it('puts services in trouble first and says how many', async () => {
    vi.mocked(getServiceMetrics).mockResolvedValue([metric('auth_service'), metric('payment_service', { errorRate: 0.12, requests: 5 })]);
    render(<ServiceMetricsPage />);
    expect(await screen.findByText(/1 service has errors above 5%/)).toBeInTheDocument();
    const rows = screen.getAllByRole('row').slice(1);
    expect(rows[0]).toHaveTextContent('payment_service');
    expect(rows[1]).toHaveTextContent('1,200');
  });
});
