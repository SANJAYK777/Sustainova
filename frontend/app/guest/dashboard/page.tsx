'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '../../../services/api';
import { useToast } from '../../../components/ToastContext';
import { useAuth } from '../../../context/AuthContext';
import LeafletLocationMap from '../../../components/LeafletLocationMap';

interface GuestEvent {
  guest_qr_token?: string | null;
  guest_qr_code_url?: string | null;
  event_name: string;
  event_date: string | null;
  location: string;
  hall_name: string;
  bus_routes: string;
  bus_stops: string;
  latitude?: number | null;
  longitude?: number | null;
  invitation_image?: string | null;
  invitation_image_url?: string | null;
}

export default function GuestDashboard() {
  const router = useRouter();
  const { showToast } = useToast();
  const { token, role, loading: authLoading } = useAuth();
  const [event, setEvent] = useState<GuestEvent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showSosConfirm, setShowSosConfirm] = useState(false);

  const goLogin = () => {
    router.push('/login');
  };

  const triggerSOS = async () => {
    if (role !== 'guest') {
      showToast('Action not permitted', 'error');
      return;
    }

    try {
      await api.post('/sos/trigger');
      showToast('Emergency alert sent to organizer', 'success');
    } catch (err: any) {
      const status = err.response?.status;
      if (status === 401 || status === 403) {
        showToast('Action not permitted', 'error');
        return;
      }
      showToast('Unable to send emergency alert', 'error');
    }
  };

  useEffect(() => {
    if (authLoading) return;
    if (!token) {
      goLogin();
      return;
    }
  }, [authLoading, token, router]);

  useEffect(() => {
    if (authLoading || !token) return;

    const fetchDashboard = async () => {
      try {
        const res = await api.get('/dashboard/guest');
        setEvent(res.data);
      } catch (err: any) {
        const errorMsg = err.response?.data?.detail || 'Failed to load dashboard';
        setError(errorMsg);
      } finally {
        setLoading(false);
      }
    };

    fetchDashboard();
  }, [authLoading, token, showToast]);

  if (authLoading) return null;

  if (loading) {
    return <p className="text-center text-[var(--text-soft)] py-16">Loading event details...</p>;
  }

  if (error || !event) {
    return (
      <div className="premium-card text-red-700">
        <p>{error || 'No event found'}</p>
      </div>
    );
  }

  const eventDate = event.event_date
    ? new Date(event.event_date).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : 'Date TBD';

  const invitationUrl = event.invitation_image
    ? event.invitation_image.startsWith('http')
      ? event.invitation_image
      : `http://localhost:8000/${event.invitation_image.replace(/^\/+/, '')}`
    : event.invitation_image_url || '';
  const hasCoordinates = typeof event.latitude === 'number' && typeof event.longitude === 'number';
  const navUrl = hasCoordinates
    ? `https://www.google.com/maps/dir/?api=1&destination=${event.latitude},${event.longitude}`
    : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(event.location || event.hall_name)}`;
  const hasInviteBackground = Boolean(invitationUrl);
  const backgroundStyle = hasInviteBackground
    ? {
        backgroundImage: `url(${invitationUrl})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }
    : undefined;

  return (
    <main
      className={hasInviteBackground ? 'relative min-h-screen' : 'min-h-screen bg-gradient-to-br from-[#F8F5F0] to-[#F3EDE4]'}
      style={backgroundStyle}
    >
      {hasInviteBackground && <div className="absolute inset-0 bg-black/50 backdrop-blur-[1px]" />}

      <div className="relative z-10 max-w-4xl mx-auto px-6 py-12 space-y-8">
        <section className={hasInviteBackground ? 'premium-card bg-white/85 backdrop-blur-md' : 'premium-card'}>
          <p className="text-sm uppercase tracking-widest text-[var(--text-soft)] mb-2">Welcome to</p>
          <h1 className="font-serif text-5xl leading-tight">{event.event_name}</h1>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8 text-[var(--text-soft)]">
            <div>
              <p className="text-xs uppercase tracking-wider">Date</p>
              <p className="text-lg text-[var(--text-dark)] mt-1">{eventDate}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wider">Location</p>
              <p className="text-lg text-[var(--text-dark)] mt-1">{event.location}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wider">Hall Name</p>
              <p className="text-lg text-[var(--text-dark)] mt-1">{event.hall_name}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wider">Bus Routes</p>
              <p className="text-lg text-[var(--text-dark)] mt-1">{event.bus_routes}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wider">Bus Stops</p>
              <p className="text-lg text-[var(--text-dark)] mt-1">{event.bus_stops}</p>
            </div>
          </div>
        </section>

        {event.guest_qr_code_url && (
          <section className={hasInviteBackground ? 'premium-card text-center bg-white/85 backdrop-blur-md' : 'premium-card text-center'}>
            <h3 className="font-serif text-2xl mb-2">Your Check-In QR</h3>
            <p className="text-[var(--text-soft)] mb-5">Show this at the entrance for fast check-in.</p>
            <img
              src={event.guest_qr_code_url}
              alt="Guest check-in QR"
              className="mx-auto h-52 w-52 rounded-2xl border border-[#C6A75E]/30 bg-white p-2 shadow-md"
            />
          </section>
        )}

        <section className={hasInviteBackground ? 'premium-card text-center bg-white/85 backdrop-blur-md' : 'premium-card text-center'}>
          <h3 className="font-serif text-2xl mb-2">Need immediate help?</h3>
          <p className="text-[var(--text-soft)] mb-6">Tap SOS to instantly notify the organizer.</p>
          {role === 'guest' && (
            <button
              onClick={() => setShowSosConfirm(true)}
              className="rounded-full bg-gradient-to-r from-[#dc2626] to-[#b91c1c] px-8 py-3 text-white shadow-lg shadow-red-500/30 transition-all duration-300 hover:scale-105"
            >
              SOS
            </button>
          )}
        </section>

        <section className={hasInviteBackground ? 'premium-card bg-white/85 backdrop-blur-md' : 'premium-card'}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-serif text-2xl">Event Location Map</h3>
            <a
              href={navUrl}
              target="_blank"
              rel="noreferrer"
              className="gold-button"
            >
              Navigate to Event
            </a>
          </div>
          <p className="mt-2 text-sm text-[var(--text-soft)]">{event.location}</p>
          <div className="mt-4">
            <LeafletLocationMap latitude={event.latitude} longitude={event.longitude} />
          </div>
        </section>
      </div>

      {showSosConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 px-6">
          <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-xl">
            <h4 className="font-serif text-2xl text-[var(--text-dark)]">Confirm Emergency Alert</h4>
            <p className="mt-2 text-[var(--text-soft)]">
              Are you sure you want to trigger emergency alert?
            </p>
            <div className="mt-6 flex gap-3 justify-end">
              <button
                onClick={() => setShowSosConfirm(false)}
                className="secondary-button"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  setShowSosConfirm(false);
                  await triggerSOS();
                }}
                className="rounded-full bg-gradient-to-r from-[#dc2626] to-[#b91c1c] px-6 py-2.5 text-white shadow-md transition-all duration-300 hover:scale-105"
              >
                Trigger SOS
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

