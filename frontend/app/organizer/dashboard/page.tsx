'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '../../../services/api';
import { useToast } from '../../../components/ToastContext';
import { useAuth } from '../../../context/AuthContext';

interface GuestListItem {
  id: number;
  name: string;
  phone: string;
  number_of_people: number;
  transport_type?: string;
}

interface RoomNeededGuest {
  name: string;
  phone: string;
  number_of_people: number;
}

interface DashboardData {
  event_id: number;
  qr_code_url: string;
  total_guests: number;
  total_people: number;
  total_parking: number;
  total_rooms_needed: number;
  expected_guests: number;
  predicted_attendance: number;
  predicted_car_parking: number;
  predicted_bike_parking: number;
  predicted_rooms: number;
  food_estimate: number;
  actual: {
    total_guests: number;
    checked_in_guests: number;
    remaining_guests: number;
    real_present_count: number;
    total_people: number;
    total_car_parking: number;
    total_bike_parking: number;
    total_rooms: number;
  };
  safety: {
    safety_total_guests: number;
    safety_total_people: number;
    safety_car_parking: number;
    safety_bike_parking: number;
    safety_total_rooms: number;
  };
  parking_guests: RoomNeededGuest[];
  rooms_needed_guests: RoomNeededGuest[];
  car_parking_guests: GuestListItem[];
  bike_parking_guests: GuestListItem[];
  room_guests: GuestListItem[];
}

interface EventMeta {
  event_name: string;
  event_date: string | null;
  event_token: string | null;
}

interface SosAlert {
  id: number;
  guest_name: string;
  guest_phone: string;
  triggered_at: string;
}

export default function OrganizerDashboard() {
  const router = useRouter();
  const { showToast } = useToast();
  const { token, role, loading: authLoading } = useAuth();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [eventMeta, setEventMeta] = useState<EventMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sosAlerts, setSosAlerts] = useState<SosAlert[]>([]);
  const [pollingEnabled, setPollingEnabled] = useState(true);
  const previousSosCount = useRef(0);

  const syncSosCount = (count: number) => {
    localStorage.setItem('sos_active_count', String(count));
    window.dispatchEvent(new Event('sos-count-updated'));
  };

  const fetchSos = async (eventId: number) => {
    const res = await api.get(`/sos/active/${eventId}`);
    const alerts: SosAlert[] = res.data || [];

    if (previousSosCount.current === 0 && alerts.length > 0) {
      try {
        await new Audio('/alert.mp3').play();
      } catch {
        // no-op
      }
    }

    previousSosCount.current = alerts.length;
    setSosAlerts(alerts);
    syncSosCount(alerts.length);
  };

  useEffect(() => {
    if (authLoading) return;
    if (!token || role !== 'organizer') {
      router.replace('/login');
      return;
    }
  }, [authLoading, token, role, router]);

  useEffect(() => {
    if (authLoading || !token || role !== 'organizer') return;

    const fetchDashboard = async () => {
      try {
        const [dashboardRes, eventsRes] = await Promise.all([
          api.get('/dashboard/organizer'),
          api.get('/events/'),
        ]);

        const loadedDashboard: DashboardData = dashboardRes.data;
        setDashboard(loadedDashboard);

        const firstEvent = eventsRes.data?.[0];
        if (firstEvent) {
          setEventMeta({
            event_name: firstEvent.event_name,
            event_date: firstEvent.event_date || null,
            event_token: firstEvent.event_token || null,
          });
        }

        await fetchSos(loadedDashboard.event_id);
      } catch (err: any) {
        setError('Unable to load organizer dashboard');
        showToast('Unable to load organizer dashboard', 'error');
      } finally {
        setLoading(false);
      }
    };

    fetchDashboard();
  }, [authLoading, token, role, showToast]);

  useEffect(() => {
    if (!dashboard?.event_id || !pollingEnabled) return;

    const interval = setInterval(async () => {
      try {
        await fetchSos(dashboard.event_id);
      } catch (err: any) {
        if (err.response?.status === 401 || err.response?.status === 403) return;
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [dashboard?.event_id, pollingEnabled]);

  useEffect(() => () => syncSosCount(0), []);

  const resolveSOS = async (id: number) => {
    try {
      await api.put(`/sos/resolve/${id}`);
      if (dashboard?.event_id) {
        await fetchSos(dashboard.event_id);
      }
    } catch (err: any) {
      if (err.response?.status === 401 || err.response?.status === 403) {
        showToast('Action not permitted', 'error');
        return;
      }
      showToast('Unable to resolve alert right now', 'error');
    }
  };

  const formatDate = (value: string | null | undefined) => {
    if (!value) return 'Date TBD';
    return new Date(value).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const formatTime = (value: string) =>
    new Date(value + 'Z').toLocaleString('en-IN', {
      timeZone: 'Asia/Kolkata',
      dateStyle: 'medium',
      timeStyle: 'short',
    });

  const statCards = dashboard
    ? [
        { label: 'Total Guests', value: dashboard.actual.total_guests, icon: 'TG' },
        { label: 'Checked In', value: dashboard.actual.checked_in_guests, icon: 'CI' },
        { label: 'Remaining', value: dashboard.actual.remaining_guests, icon: 'RM' },
        { label: 'Real Present', value: dashboard.actual.real_present_count, icon: 'RP' },
      ]
    : [];

  const renderTable = (title: string, rows: GuestListItem[]) => (
    <div className="premium-card section-fade overflow-hidden">
      <h3 className="mb-5 font-serif text-2xl">{title}</h3>
      {rows.length === 0 ? (
        <p className="text-[var(--text-soft)]">No records found.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-[rgba(198,167,94,0.25)] text-sm text-[var(--text-soft)]">
                <th className="py-3 pr-4">Name</th>
                <th className="py-3 pr-4">Phone</th>
                <th className="py-3 pr-4">People</th>
                <th className="py-3">Transport</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr
                  key={row.id}
                  className={`${index % 2 === 0 ? 'bg-[#fbf8f2]' : 'bg-white'} border-b border-[rgba(198,167,94,0.15)]`}
                >
                  <td className="py-3 pr-4">{row.name}</td>
                  <td className="py-3 pr-4">{row.phone}</td>
                  <td className="py-3 pr-4">{row.number_of_people}</td>
                  <td className="py-3">{row.transport_type || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );

  if (authLoading) return null;

  if (loading) {
    return <p className="py-16 text-center text-[var(--text-soft)]">Loading dashboard...</p>;
  }

  if (error || !dashboard) {
    return (
      <div className="premium-card text-red-700">
        <p>{error || 'Failed to load dashboard'}</p>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <section className="section-fade premium-card">
        <div className="grid grid-cols-1 items-center gap-6 md:grid-cols-[1fr_auto]">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-[var(--text-soft)]">Organizer Dashboard</p>
            <h1 className="mt-3 font-serif text-4xl text-[var(--text-dark)] sm:text-5xl">
              {eventMeta?.event_name || 'Event'}
            </h1>
            <p className="mt-3 text-[var(--text-soft)]">{formatDate(eventMeta?.event_date)}</p>
            {eventMeta?.event_token && (
              <button
                onClick={() => router.push(`/entrance/${eventMeta.event_token}`)}
                className="gold-button mt-5"
              >
                Open Entrance Scanner
              </button>
            )}
          </div>
          {dashboard.qr_code_url && (
            <img
              src={dashboard.qr_code_url}
              alt="Event QR"
              className="h-36 w-36 rounded-2xl border border-[#C6A75E]/30 shadow-md"
            />
          )}
        </div>
      </section>

      <section className="section-fade">
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {statCards.map((card) => (
            <article
              key={card.label}
              className="rounded-3xl border border-[#C6A75E]/20 bg-gradient-to-br from-white to-[#faf8f2] p-8 shadow-lg shadow-black/5 transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-black/10"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm text-[var(--text-soft)]">{card.label}</p>
                  <p className="mt-2 font-serif text-4xl text-[var(--primary)]">{card.value}</p>
                </div>
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-[#1F4F46]/10 text-xs font-bold text-[#1F4F46]">
                  {card.icon}
                </span>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="section-fade rounded-3xl border border-[#C6A75E]/35 bg-red-50 p-6 shadow-md">
        <h2 className="text-2xl font-semibold text-red-700">SOS Alerts</h2>
        {sosAlerts.length === 0 ? (
          <p className="mt-2 text-[var(--text-soft)]">No active SOS alerts.</p>
        ) : (
          <div className="mt-4 space-y-4">
            {sosAlerts.map((alert) => (
              <div
                key={alert.id}
                className="animate-pulse rounded-3xl border border-red-500 bg-red-50 p-5 shadow-md"
              >
                <p className="text-lg font-semibold text-red-700">SOS ALERT</p>
                <p className="mt-2 text-[var(--text-dark)]">Guest: {alert.guest_name}</p>
                <p className="text-[var(--text-dark)]">Phone: {alert.guest_phone}</p>
                <p className="text-[var(--text-soft)]">Time: {formatTime(alert.triggered_at)}</p>
                <button
                  onClick={() => resolveSOS(alert.id)}
                  className="gold-button mt-3"
                >
                  Resolve
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="section-fade premium-card">
        <h2 className="font-serif text-3xl">Safety Planning (20% Buffer)</h2>
        <p className="mb-6 mt-2 text-sm text-[var(--text-soft)]">Planning values with built-in safety margin.</p>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ['Guests', dashboard.safety.safety_total_guests],
            ['People', dashboard.safety.safety_total_people],
            ['Car Parking', dashboard.safety.safety_car_parking],
            ['Bike Parking', dashboard.safety.safety_bike_parking],
            ['Rooms', dashboard.safety.safety_total_rooms],
          ].map(([label, value]) => (
            <div key={String(label)} className="rounded-2xl border border-[#C6A75E]/20 bg-[#fffdf8] p-5 shadow-md transition-all duration-300 hover:shadow-lg">
              <p className="text-sm text-[var(--text-soft)]">{label}</p>
              <p className="mt-2 font-serif text-3xl text-[var(--primary)]">{value}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="section-fade premium-card">
        <h2 className="font-serif text-3xl">ML Attendance Forecast (XGBoost)</h2>
        <p className="mb-6 mt-2 text-sm text-[var(--text-soft)]">Predicted operational requirements based on RSVP behavior.</p>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {[
            ['Expected Guests', dashboard.expected_guests],
            ['Predicted Attendance', dashboard.predicted_attendance],
            ['Car Parking Needed', dashboard.predicted_car_parking],
            ['Bike Parking Needed', dashboard.predicted_bike_parking],
            ['Rooms Required', dashboard.predicted_rooms],
            ['Food Preparation Estimate', dashboard.food_estimate],
          ].map(([label, value]) => (
            <div
              key={String(label)}
              className="rounded-2xl border border-[#C6A75E]/20 bg-[#fffdf8] p-5 shadow-md transition-all duration-300 hover:shadow-lg"
            >
              <p className="text-sm text-[var(--text-soft)]">{label}</p>
              <p className="mt-2 font-serif text-3xl text-[var(--primary)]">{value}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        {renderTable('Car Parking Guests', dashboard.car_parking_guests)}
        {renderTable('Bike Parking Guests', dashboard.bike_parking_guests)}
      </section>

      <section className="rounded-xl shadow-md border p-4 section-fade">
        <h3 className="mb-4 font-serif text-2xl">Guests Needing Rooms</h3>
        {dashboard.rooms_needed_guests.length === 0 ? (
          <p className="text-[var(--text-soft)]">No guests requested rooms.</p>
        ) : (
          <div className="max-h-[300px] overflow-y-auto rounded-xl border">
            <table className="w-full border-collapse text-left">
              <thead className="sticky top-0 bg-[#fffdf8]">
                <tr className="border-b border-[rgba(198,167,94,0.25)] text-sm text-[var(--text-soft)]">
                  <th className="py-3 px-3">Name</th>
                  <th className="py-3 px-3">Phone</th>
                  <th className="py-3 px-3">People</th>
                </tr>
              </thead>
              <tbody>
                {dashboard.rooms_needed_guests.map((guest, idx) => (
                  <tr
                    key={`${guest.phone}-${idx}`}
                    className={`${idx % 2 === 0 ? 'bg-[#fbf8f2]' : 'bg-white'} border-b border-[rgba(198,167,94,0.15)]`}
                  >
                    <td className="py-3 px-3">{guest.name}</td>
                    <td className="py-3 px-3">{guest.phone}</td>
                    <td className="py-3 px-3">{guest.number_of_people}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

