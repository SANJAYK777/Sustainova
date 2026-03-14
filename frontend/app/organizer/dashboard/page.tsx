'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Bar, Doughnut, Pie } from 'react-chartjs-2';
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip,
} from 'chart.js';
import api from '../../../services/api';
import { useToast } from '../../../components/ToastContext';
import { useAuth } from '../../../context/AuthContext';

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, Tooltip, Legend);

interface GuestListItem {
  id: number;
  name: string;
  phone: string;
  number_of_people: number;
  coming_from?: string | null;
  transport_type?: string;
  vehicle_number?: string | null;
}

interface RoomNeededGuest {
  name: string;
  room_required: string;
  room_type?: string | null;
  aadhar_number?: string | null;
}

interface DashboardData {
  event_id: number;
  qr_code_url: string;
  total_guests: number;
  total_people: number;
  total_parking: number;
  total_rooms_needed: number;
  car_parking_needed: number;
  bike_parking_needed: number;
  expected_guests: number;
  predicted_attendance: number;
  predicted_car_parking: number;
  predicted_bike_parking: number;
  predicted_rooms: number;
  food_estimate: number;
  travel_risk: {
    Predicted_Attendance: number;
    Local_Guests_Count: number;
    Outstation_Guests_Count: number;
    Travel_Risk_Level: 'Low' | 'Medium' | 'High';
  };
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
  parking_guests: RoomNeededGuest[];
  rooms_needed_guests: RoomNeededGuest[];
  car_parking_guests: GuestListItem[];
  bike_parking_guests: GuestListItem[];
  room_guests: GuestListItem[];
}

interface AnalyticsData {
  event_id: number;
  locations: Record<string, number>;
  vehicle_types: Record<string, number>;
  room_types: Record<string, number>;
  checkin_status: Record<string, number>;
}

interface LocationDistributionPoint {
  location: string;
  guests: number;
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
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [locationDistribution, setLocationDistribution] = useState<LocationDistributionPoint[]>([]);
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

  const fetchAnalytics = async () => {
    const res = await api.get('/api/dashboard-analytics');
    setAnalytics(res.data || null);
  };

  const fetchGuestLocationDistribution = async () => {
    const res = await api.get('/api/guest-location-distribution');
    setLocationDistribution(Array.isArray(res.data) ? res.data : []);
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
        await fetchAnalytics();
        await fetchGuestLocationDistribution();
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
        await fetchAnalytics();
        await fetchGuestLocationDistribution();
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

  const exportGuestList = async () => {
    if (!dashboard) return;
    try {
      const res = await api.get(`/guests/export/${dashboard.event_id}`, {
        responseType: 'blob',
      });
      const blobUrl = window.URL.createObjectURL(new Blob([res.data], { type: 'text/csv' }));
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = `guest_list_event_${dashboard.event_id}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch {
      showToast('Unable to export guest list right now', 'error');
    }
  };

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
                <th className="py-3 pr-4">Coming From</th>
                <th className="py-3">Transport</th>
                <th className="py-3">Vehicle Number</th>
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
                  <td className="py-3 pr-4">{row.coming_from || '-'}</td>
                  <td className="py-3">{row.transport_type || '-'}</td>
                  <td className="py-3">{row.vehicle_number || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );

  const palette = ['#1F4F46', '#C6A75E', '#2C7A7B', '#A8552A', '#64748B', '#94A3B8'];
  const locationEntries = Object.entries(analytics?.locations || {});
  const vehicleEntries = Object.entries(analytics?.vehicle_types || {});
  const roomEntries = Object.entries(analytics?.room_types || {});
  const checkedInCount = analytics?.checkin_status?.['Checked-in'] || 0;
  const notCheckedInCount = analytics?.checkin_status?.['Not checked-in'] || 0;
  const checkinTotal = checkedInCount + notCheckedInCount;
  const checkinPercent = checkinTotal > 0 ? Math.round((checkedInCount / checkinTotal) * 100) : 0;

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
            <div className="text-center">
              <img
                src={dashboard.qr_code_url}
                alt="Event QR"
                className="mx-auto h-36 w-36 rounded-2xl border border-[#C6A75E]/30 shadow-md"
              />
              <a
                href={dashboard.qr_code_url}
                download={`event_qr_${dashboard.event_id}.png`}
                className="mt-3 inline-block bg-emerald-600 text-white px-4 py-2 rounded-xl hover:bg-emerald-700 transition"
              >
                Download QR Code
              </a>
            </div>
          )}
        </div>
      </section>

      <section className="section-fade">
        <div className="mb-4 flex justify-end">
          <button
            onClick={exportGuestList}
            className="bg-blue-600 text-white px-4 py-2 rounded-xl hover:bg-blue-700 transition"
          >
            Export Guest List
          </button>
        </div>
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
        <h2 className="font-serif text-3xl">Predicted Count</h2>
        <p className="mb-6 mt-2 text-sm text-[var(--text-soft)]">Predicted operational requirements based on RSVP behavior.</p>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {[
            ['Expected Guests', dashboard.expected_guests],
            ['Predicted Attendance', dashboard.predicted_attendance],
            ['Car Parking Needed', dashboard.car_parking_needed],
            ['Bike Parking Needed', dashboard.bike_parking_needed],
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

      <section className="section-fade premium-card">
        <h2 className="font-serif text-3xl">Travel Risk Prediction</h2>
        <p className="mb-6 mt-2 text-sm text-[var(--text-soft)]">Rule-based attendance adjustment using guest travel distance.</p>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ['Predicted Attendance', dashboard.travel_risk.Predicted_Attendance],
            ['Local Guests', dashboard.travel_risk.Local_Guests_Count],
            ['Outstation Guests', dashboard.travel_risk.Outstation_Guests_Count],
            ['Travel Risk Level', dashboard.travel_risk.Travel_Risk_Level],
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

      <section className="section-fade premium-card">
        <h2 className="font-serif text-3xl">Event Analytics</h2>
        <p className="mb-6 mt-2 text-sm text-[var(--text-soft)]">Live guest analytics inspired by BI dashboards.</p>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <article className="rounded-2xl border border-[#C6A75E]/20 bg-[#fffdf8] p-5 shadow-md">
            <h3 className="font-semibold text-lg text-[var(--text-dark)]">Guest Location Distribution</h3>
            <div className="mt-4 h-72">
              {locationEntries.length > 0 ? (
                <Pie
                  data={{
                    labels: locationEntries.map(([label]) => label),
                    datasets: [
                      {
                        data: locationEntries.map(([, value]) => value),
                        backgroundColor: palette,
                        borderColor: '#ffffff',
                        borderWidth: 1,
                      },
                    ],
                  }}
                  options={{ maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }}
                />
              ) : (
                <p className="text-[var(--text-soft)]">No location data available.</p>
              )}
            </div>
          </article>

          <article className="rounded-2xl border border-[#C6A75E]/20 bg-[#fffdf8] p-5 shadow-md">
            <h3 className="font-semibold text-lg text-[var(--text-dark)]">Vehicle Type Distribution</h3>
            <div className="mt-4 h-72">
              {vehicleEntries.length > 0 ? (
                <Bar
                  data={{
                    labels: vehicleEntries.map(([label]) => label),
                    datasets: [
                      {
                        label: 'Guests',
                        data: vehicleEntries.map(([, value]) => value),
                        backgroundColor: ['#1F4F46', '#2C7A7B', '#C6A75E'],
                        borderRadius: 8,
                      },
                    ],
                  }}
                  options={{
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
                  }}
                />
              ) : (
                <p className="text-[var(--text-soft)]">No vehicle data available.</p>
              )}
            </div>
          </article>

          <article className="rounded-2xl border border-[#C6A75E]/20 bg-[#fffdf8] p-5 shadow-md">
            <h3 className="font-semibold text-lg text-[var(--text-dark)]">Room Requirement Distribution</h3>
            <div className="mt-4 h-72">
              {roomEntries.length > 0 ? (
                <Doughnut
                  data={{
                    labels: roomEntries.map(([label]) => label),
                    datasets: [
                      {
                        data: roomEntries.map(([, value]) => value),
                        backgroundColor: ['#C6A75E', '#1F4F46', '#2C7A7B'],
                        borderColor: '#ffffff',
                        borderWidth: 1,
                      },
                    ],
                  }}
                  options={{
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'bottom' } },
                    cutout: '60%',
                  }}
                />
              ) : (
                <p className="text-[var(--text-soft)]">No room data available.</p>
              )}
            </div>
          </article>

          <article className="rounded-2xl border border-[#C6A75E]/20 bg-[#fffdf8] p-5 shadow-md">
            <h3 className="font-semibold text-lg text-[var(--text-dark)]">Guest Check-in Status</h3>
            <div className="mt-6 space-y-5">
              <div>
                <div className="mb-2 flex items-center justify-between text-sm text-[var(--text-soft)]">
                  <span>Checked-in guests</span>
                  <span>{checkedInCount}</span>
                </div>
                <div className="h-3 w-full rounded-full bg-[#e5e7eb]">
                  <div
                    className="h-3 rounded-full bg-[var(--emerald)] transition-all"
                    style={{ width: `${checkinPercent}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="mb-2 flex items-center justify-between text-sm text-[var(--text-soft)]">
                  <span>Not checked-in guests</span>
                  <span>{notCheckedInCount}</span>
                </div>
                <div className="h-3 w-full rounded-full bg-[#e5e7eb]">
                  <div
                    className="h-3 rounded-full bg-[#C6A75E] transition-all"
                    style={{ width: `${100 - checkinPercent}%` }}
                  />
                </div>
              </div>

              <p className="text-sm text-[var(--text-soft)]">Total tracked guests: {checkinTotal}</p>
            </div>
          </article>
        </div>
      </section>

      <section className="section-fade premium-card">
        <h2 className="font-serif text-3xl">Guest Location Distribution</h2>
        <p className="mb-6 mt-2 text-sm text-[var(--text-soft)]">Guest count grouped by coming-from location.</p>
        {locationDistribution.length > 0 ? (
          <div className="h-80">
            <Bar
              data={{
                labels: locationDistribution.map((item) => item.location),
                datasets: [
                  {
                    label: 'Guests',
                    data: locationDistribution.map((item) => item.guests),
                    backgroundColor: '#1F4F46',
                    borderRadius: 8,
                  },
                ],
              }}
              options={{
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: { legend: { display: false } },
                scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
              }}
            />
          </div>
        ) : (
          <p className="text-[var(--text-soft)]">No location data available yet.</p>
        )}
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
                  <th className="py-3 px-3">Room Required</th>
                  <th className="py-3 px-3">Room Type</th>
                  <th className="py-3 px-3">Aadhar Number</th>
                </tr>
              </thead>
              <tbody>
                {dashboard.rooms_needed_guests.map((guest, idx) => (
                  <tr
                    key={`${guest.name}-${idx}`}
                    className={`${idx % 2 === 0 ? 'bg-[#fbf8f2]' : 'bg-white'} border-b border-[rgba(198,167,94,0.15)]`}
                  >
                    <td className="py-3 px-3">{guest.name}</td>
                    <td className="py-3 px-3">{guest.room_required}</td>
                    <td className="py-3 px-3">{guest.room_type || '-'}</td>
                    <td className="py-3 px-3">{guest.aadhar_number || '-'}</td>
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

