'use client';

import { AxiosError } from 'axios';
import { useEffect, useMemo, useState } from 'react';
import { Bar, Pie } from 'react-chartjs-2';
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Title,
  Tooltip,
} from 'chart.js';
import api from '../../../services/api';
import { useToast } from '../../../components/ToastContext';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend, ArcElement);

type Summary = {
  total_rsvps: number;
  actual_attendance: number;
  predicted_attendance: number;
  predicted_food: number;
  actual_food: number;
  predicted_parking: number;
  predicted_rooms: number;
  transport_distribution: Record<string, number>;
  waste_saved: number;
  co2_saved: number;
  money_saved: number;
};

type ApiError = { detail?: string };

export default function DashboardPage({ params }: { params: { eventId: string } }) {
  const { eventId } = params;
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { showToast } = useToast();

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId]);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get<Summary>(`/dashboard/summary/${eventId}`);
      setData(res.data);
      showToast('Dashboard loaded', 'success');
    } catch (err) {
      const apiErr = err as AxiosError<ApiError>;
      const msg = apiErr.response?.data?.detail || 'Unable to load dashboard.';
      setError(msg);
      showToast(msg, 'error');
    } finally {
      setLoading(false);
    }
  };

  const barData = useMemo(() => {
    if (!data) return null;
    return {
      labels: ['Predicted', 'Actual'],
      datasets: [
        {
          label: 'Attendance',
          data: [data.predicted_attendance, data.actual_attendance],
          backgroundColor: ['#C6A75E', '#1F4F46'],
          borderRadius: 12,
        },
      ],
    };
  }, [data]);

  const pieData = useMemo(() => {
    if (!data) return null;
    const labels = Object.keys(data.transport_distribution);
    const values = Object.values(data.transport_distribution);
    return {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: ['#1F4F46', '#C6A75E', '#A88B4C', '#b89a57'],
          borderWidth: 1,
        },
      ],
    };
  }, [data]);

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'bottom' as const },
      tooltip: { mode: 'index' as const },
    },
  };

  return (
    <main className="space-y-8">
      <header className="premium-card hover:-translate-y-2 transition-all duration-300 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.25em] text-[var(--text-soft)]">Eventify</p>
          <h1 className="font-serif text-4xl">Event Analytics</h1>
          <p className="text-sm text-[var(--text-soft)]">Event ID: {eventId}</p>
        </div>
        <button onClick={load} disabled={loading} className="gold-button disabled:opacity-60">
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </header>

      {error ? <p className="premium-card text-sm text-red-700">{error}</p> : null}

      <section className="grid gap-4 md:grid-cols-5">
        {[
          ['Total RSVPs', data?.total_rsvps ?? '-'],
          ['Predicted Attendance', data?.predicted_attendance ?? '-'],
          ['Actual Attendance', data?.actual_attendance ?? '-'],
          ['Food Saved (kg)', data ? Math.round(data.waste_saved) : '-'],
          ['CO2 Saved', data ? data.co2_saved.toFixed(1) : '-'],
        ].map(([label, value]) => (
          <div key={String(label)} className="premium-card hover:-translate-y-2 transition-all duration-300 p-6">
            <p className="text-xs uppercase tracking-wide text-[var(--text-soft)]">{label}</p>
            <p className="mt-2 font-serif text-3xl text-[var(--emerald)]">{value}</p>
          </div>
        ))}
      </section>

      <section className="grid gap-6 md:grid-cols-2">
        <div className="premium-card hover:-translate-y-2 transition-all duration-300">
          <h3 className="font-serif text-2xl">Predicted vs Actual</h3>
          <p className="text-sm text-[var(--text-soft)]">Attendance comparison</p>
          <div className="mt-4 h-72">{barData ? <Bar data={barData} options={chartOptions} /> : null}</div>
        </div>
        <div className="premium-card hover:-translate-y-2 transition-all duration-300">
          <h3 className="font-serif text-2xl">Transport Distribution</h3>
          <p className="text-sm text-[var(--text-soft)]">How guests plan to travel</p>
          <div className="mt-4 h-72">{pieData ? <Pie data={pieData} options={chartOptions} /> : null}</div>
        </div>
      </section>

      {data ? (
        <section className="grid gap-4 md:grid-cols-3">
          <div className="premium-card hover:-translate-y-2 transition-all duration-300 p-6">
            <p className="text-sm text-[var(--text-soft)]">Predicted Food</p>
            <p className="mt-1 font-serif text-3xl text-[var(--emerald)]">{data.predicted_food}</p>
            <p className="text-xs text-[var(--text-soft)]">plates</p>
          </div>
          <div className="premium-card hover:-translate-y-2 transition-all duration-300 p-6">
            <p className="text-sm text-[var(--text-soft)]">Predicted Parking</p>
            <p className="mt-1 font-serif text-3xl text-[var(--emerald)]">{data.predicted_parking}</p>
            <p className="text-xs text-[var(--text-soft)]">spots</p>
          </div>
          <div className="premium-card hover:-translate-y-2 transition-all duration-300 p-6">
            <p className="text-sm text-[var(--text-soft)]">Predicted Rooms</p>
            <p className="mt-1 font-serif text-3xl text-[var(--emerald)]">{data.predicted_rooms}</p>
            <p className="text-xs text-[var(--text-soft)]">rooms</p>
          </div>
        </section>
      ) : null}
    </main>
  );
}

