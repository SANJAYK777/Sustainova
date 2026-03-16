'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '../../../services/api';
import { useToast } from '../../../components/ToastContext';
import { useAuth } from '../../../context/AuthContext';
import LeafletLocationMap from '../../../components/LeafletLocationMap';

interface GuestEvent {
  event_id: number;
  guest_id: number;
  guest_qr_token?: string | null;
  guest_qr_code_url?: string | null;
  number_of_people: number;
  parking_type: string;
  car_count: number;
  bike_count: number;
  vehicle_number?: string | null;
  status: string;
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

interface AnnouncementItem {
  id: number;
  event_id: number;
  title: string;
  message: string;
  created_at: string;
  created_by: number;
}

export default function GuestDashboard() {
  const router = useRouter();
  const { showToast } = useToast();
  const { token, role, loading: authLoading } = useAuth();
  const [event, setEvent] = useState<GuestEvent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showSosConfirm, setShowSosConfirm] = useState(false);
  const [sosReason, setSosReason] = useState('');
  const [sosSubmitting, setSosSubmitting] = useState(false);
  const [announcements, setAnnouncements] = useState<AnnouncementItem[]>([]);
  const [showAnnouncementDropdown, setShowAnnouncementDropdown] = useState(false);
  const [unreadAnnouncementCount, setUnreadAnnouncementCount] = useState(0);
  const [popupAnnouncement, setPopupAnnouncement] = useState<AnnouncementItem | null>(null);
  const [showManageForm, setShowManageForm] = useState(false);
  const [saveLoading, setSaveLoading] = useState(false);
  const [cancelLoading, setCancelLoading] = useState(false);
  const [manageForm, setManageForm] = useState({
    number_of_people: '1',
    vehicle_type: 'None',
    vehicle_count: '1',
    vehicle_number: '',
  });
  const [countdownText, setCountdownText] = useState('');
  const popupTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const goLogin = () => {
    router.push('/login');
  };

  const fetchGuestDashboard = async () => {
    const res = await api.get('/dashboard/guest');
    const data = res.data as GuestEvent;
    setEvent(data);
    const vehicleCount =
      (data.parking_type || '').toLowerCase() === 'car'
        ? Math.max(1, Number(data.car_count || 1))
        : (data.parking_type || '').toLowerCase() === 'bike'
          ? Math.max(1, Number(data.bike_count || 1))
          : 1;
    setManageForm({
      number_of_people: String(Math.max(1, Number(data.number_of_people || 1))),
      vehicle_type: data.parking_type || 'None',
      vehicle_count: String(vehicleCount),
      vehicle_number: data.vehicle_number || '',
    });
  };

  const triggerSOS = async () => {
    if (role !== 'guest') {
      showToast('Action not permitted', 'error');
      return;
    }

    const trimmedReason = sosReason.trim();
    if (!trimmedReason) {
      showToast('Please enter SOS reason', 'error');
      return;
    }

    setSosSubmitting(true);
    try {
      await api.post('/sos/trigger', { reason: trimmedReason });
      showToast('Emergency alert sent to organizer', 'success');
      setSosReason('');
      setShowSosConfirm(false);
    } catch (err: any) {
      const status = err.response?.status;
      if (status === 401 || status === 403) {
        showToast('Action not permitted', 'error');
        return;
      }
      showToast('Unable to send emergency alert', 'error');
    } finally {
      setSosSubmitting(false);
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
        await fetchGuestDashboard();
      } catch (err: any) {
        const errorMsg = err.response?.data?.detail || 'Failed to load dashboard';
        setError(errorMsg);
      } finally {
        setLoading(false);
      }
    };

    fetchDashboard();
  }, [authLoading, token, showToast]);

  useEffect(() => {
    if (!event?.event_date) {
      setCountdownText('');
      return;
    }

    const eventDate = new Date(event.event_date);

    const updateCountdown = () => {
      const now = new Date();
      const diff = eventDate.getTime() - now.getTime();

      if (diff <= 0) {
        setCountdownText('Wedding is happening now!');
        return;
      }

      const totalSeconds = Math.floor(diff / 1000);
      const days = Math.floor(totalSeconds / (24 * 60 * 60));
      const hours = Math.floor((totalSeconds % (24 * 60 * 60)) / (60 * 60));
      const minutes = Math.floor((totalSeconds % (60 * 60)) / 60);
      const seconds = totalSeconds % 60;

      setCountdownText(`${days} Days ${hours} Hours ${minutes} Minutes ${seconds} Seconds`);
    };

    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);

    return () => clearInterval(interval);
  }, [event?.event_date]);

  useEffect(() => {
    if (!token || !event?.event_id) return;

    const fetchAnnouncements = async () => {
      try {
        const res = await api.get(`/api/announcements/${event.event_id}`);
        setAnnouncements(Array.isArray(res.data) ? res.data : []);
      } catch (err: any) {
        const status = err.response?.status;
        if (status === 401 || status === 403 || status === 404) return;
        showToast('Unable to load announcements right now', 'error');
      }
    };

    fetchAnnouncements();
  }, [token, event?.event_id, showToast]);

  useEffect(() => {
    if (!token || !event?.event_id) return;

    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const wsBase = apiBase.startsWith('https://')
      ? apiBase.replace(/^https/, 'wss')
      : apiBase.replace(/^http/, 'ws');
    const socket = new WebSocket(`${wsBase}/ws/announcements/${event.event_id}?token=${encodeURIComponent(token)}`);

    socket.onmessage = (evt) => {
      try {
        const payload = JSON.parse(evt.data);
        if (payload?.type !== 'announcement_created' || !payload?.announcement) return;

        const incoming: AnnouncementItem = payload.announcement;
        setAnnouncements((prev) => {
          if (prev.some((item) => item.id === incoming.id)) return prev;
          return [incoming, ...prev];
        });
        setUnreadAnnouncementCount((prev) => prev + 1);
        setPopupAnnouncement(incoming);

        if (popupTimeoutRef.current) {
          clearTimeout(popupTimeoutRef.current);
        }
        popupTimeoutRef.current = setTimeout(() => {
          setPopupAnnouncement(null);
        }, 5000);
      } catch {
        // no-op
      }
    };

    return () => {
      if (popupTimeoutRef.current) {
        clearTimeout(popupTimeoutRef.current);
      }
      socket.close();
    };
  }, [token, event?.event_id]);

  const saveRegistrationChanges = async () => {
    if (!event) return;
    const numberOfPeople = Number(manageForm.number_of_people);
    const vehicleCount = Number(manageForm.vehicle_count);
    const vehicleType = manageForm.vehicle_type;

    if (numberOfPeople < 1) {
      showToast('Number of people must be at least 1', 'error');
      return;
    }
    if ((vehicleType === 'Car' || vehicleType === 'Bike') && vehicleCount < 1) {
      showToast('Vehicle count must be at least 1', 'error');
      return;
    }

    setSaveLoading(true);
    try {
      await api.put(`/api/guest/update/${event.guest_id}`, {
        number_of_people: numberOfPeople,
        vehicle_type: vehicleType,
        vehicle_count: vehicleType === 'None' ? null : vehicleCount,
        vehicle_number: vehicleType === 'None' ? null : (manageForm.vehicle_number.trim() || null),
      });
      await fetchGuestDashboard();
      setShowManageForm(false);
      showToast('Registration updated', 'success');
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Unable to update registration';
      showToast(msg, 'error');
    } finally {
      setSaveLoading(false);
    }
  };

  const cancelRegistration = async () => {
    if (!event) return;
    const confirmed = window.confirm('Are you sure you want to cancel your registration?');
    if (!confirmed) return;

    setCancelLoading(true);
    try {
      await api.put(`/api/guest/cancel/${event.guest_id}`);
      await fetchGuestDashboard();
      setShowManageForm(false);
      showToast('Registration cancelled', 'success');
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Unable to cancel registration';
      showToast(msg, 'error');
    } finally {
      setCancelLoading(false);
    }
  };

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

  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const invitationUrl = event.invitation_image
    ? event.invitation_image.startsWith('http')
      ? event.invitation_image
      : `${apiBaseUrl}/${event.invitation_image.replace(/^\/+/, '')}`
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
  const formatAnnouncementTime = (value: string) =>
    new Date(value).toLocaleString('en-IN', {
      timeZone: 'Asia/Kolkata',
      dateStyle: 'medium',
      timeStyle: 'short',
    });

  return (
    <main
      className={hasInviteBackground ? 'relative min-h-screen' : 'min-h-screen bg-gradient-to-br from-[#F8F5F0] to-[#F3EDE4]'}
      style={backgroundStyle}
    >
      {hasInviteBackground && <div className="absolute inset-0 bg-black/50 backdrop-blur-[1px]" />}

      <div className="relative z-10 max-w-4xl mx-auto px-6 py-12 space-y-8">
        <section className={hasInviteBackground ? 'premium-card bg-white/85 backdrop-blur-md' : 'premium-card'}>
          <div className="mb-2 flex items-center justify-between gap-4">
            <p className="text-sm uppercase tracking-widest text-[var(--text-soft)]">Welcome to</p>
            <div className="relative">
              <button
                onClick={() => {
                  setShowAnnouncementDropdown((prev) => !prev);
                  setUnreadAnnouncementCount(0);
                }}
                className="relative rounded-full border border-[rgba(198,167,94,0.35)] bg-white px-3 py-2 text-lg shadow-sm"
                aria-label="Announcements"
              >
                🔔
                {unreadAnnouncementCount > 0 && (
                  <span className="absolute -right-1 -top-1 inline-flex min-h-[18px] min-w-[18px] items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold text-white">
                    {unreadAnnouncementCount}
                  </span>
                )}
              </button>
              {showAnnouncementDropdown && (
                <div className="absolute right-0 z-20 mt-2 w-80 max-h-80 overflow-y-auto rounded-2xl border border-[rgba(198,167,94,0.25)] bg-white p-3 shadow-xl">
                  <p className="mb-2 text-xs uppercase tracking-wider text-[var(--text-soft)]">Announcements</p>
                  {announcements.length === 0 ? (
                    <p className="text-sm text-[var(--text-soft)]">No announcements yet.</p>
                  ) : (
                    <div className="space-y-2">
                      {announcements.map((item) => (
                        <article key={item.id} className="rounded-xl border border-[rgba(198,167,94,0.2)] bg-[#fffdf8] p-2.5">
                          <h4 className="text-sm font-semibold text-[var(--text-dark)]">{item.title}</h4>
                          <p className="mt-1 line-clamp-2 text-xs text-[var(--text-dark)]">{item.message}</p>
                          <p className="mt-1 text-[10px] text-[var(--text-soft)]">{formatAnnouncementTime(item.created_at)}</p>
                        </article>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
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
          <section className="rounded-2xl shadow-xl p-6 bg-white text-center">
            <h3 className="font-serif text-2xl mb-2">Your Check-In QR Code</h3>
            <p className="text-[var(--text-soft)] mb-5">Show this at the entrance for fast check-in.</p>
            <div className="text-center">
              <img
                src={event.guest_qr_code_url}
                alt="Guest check-in QR"
                className="w-48 h-48 mx-auto rounded-2xl border border-[#C6A75E]/30 bg-white p-2"
              />
              <a
                href={event.guest_qr_code_url}
                download="guest_checkin_qr.png"
                className="mt-4 inline-block bg-emerald-600 text-white px-5 py-2 rounded-xl hover:bg-emerald-700 transition"
              >
                Download Check-In QR
              </a>
            </div>
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

        {event.event_date && (
          <section className="bg-gradient-to-r from-emerald-500 to-teal-600 text-white rounded-2xl p-6 shadow-lg text-center">
            <h3 className="font-serif text-3xl mb-2">Wedding starts in:</h3>
            <p className="text-lg">{countdownText}</p>
          </section>
        )}

        <section className={hasInviteBackground ? 'premium-card bg-white/85 backdrop-blur-md' : 'premium-card'}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-serif text-2xl">Manage Registration</h3>
            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold ${
                (event.status || 'registered').toLowerCase() === 'cancelled'
                  ? 'bg-red-100 text-red-700'
                  : 'bg-emerald-100 text-emerald-700'
              }`}
            >
              {(event.status || 'registered').toLowerCase() === 'cancelled' ? 'Cancelled' : 'Registered'}
            </span>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            <p className="text-[var(--text-soft)]">
              <span className="font-semibold text-[var(--text-dark)]">Number of People Attending:</span>{' '}
              {event.number_of_people}
            </p>
            <p className="text-[var(--text-soft)]">
              <span className="font-semibold text-[var(--text-dark)]">Vehicle Type:</span>{' '}
              {event.parking_type || 'None'}
            </p>
            <p className="text-[var(--text-soft)]">
              <span className="font-semibold text-[var(--text-dark)]">Vehicle Count:</span>{' '}
              {(event.parking_type || '').toLowerCase() === 'car'
                ? event.car_count
                : (event.parking_type || '').toLowerCase() === 'bike'
                  ? event.bike_count
                  : 0}
            </p>
            <p className="text-[var(--text-soft)]">
              <span className="font-semibold text-[var(--text-dark)]">Parking Requirement:</span>{' '}
              {(event.parking_type || '').toLowerCase() === 'none' ? 'No Parking' : `${event.parking_type} Parking`}
            </p>
            <p className="text-[var(--text-soft)]">
              <span className="font-semibold text-[var(--text-dark)]">Vehicle Number:</span>{' '}
              {event.vehicle_number || '-'}
            </p>
          </div>

          {(event.status || 'registered').toLowerCase() !== 'cancelled' && (
            <div className="mt-5 flex flex-wrap gap-3">
              <button
                onClick={() => setShowManageForm((prev) => !prev)}
                className="gold-button"
              >
                Update Details
              </button>
              <button
                onClick={cancelRegistration}
                disabled={cancelLoading}
                className="danger-button disabled:opacity-60"
              >
                {cancelLoading ? 'Cancelling...' : 'Cancel Registration'}
              </button>
            </div>
          )}

          {showManageForm && (event.status || 'registered').toLowerCase() !== 'cancelled' && (
            <div className="form-stack mt-5 rounded-2xl border border-[#C6A75E]/20 bg-[#fffdf8] p-4">
              <label className="form-label">Number of People</label>
              <input
                type="number"
                min={1}
                step={1}
                value={manageForm.number_of_people}
                onChange={(e) => setManageForm((prev) => ({ ...prev, number_of_people: e.target.value }))}
                className="premium-input number-spinner"
                placeholder="Number of People Attending"
              />
              <label className="form-label">Vehicle Type</label>
              <select
                value={manageForm.vehicle_type}
                onChange={(e) => {
                  const nextType = e.target.value;
                  setManageForm((prev) => ({
                    ...prev,
                    vehicle_type: nextType,
                    vehicle_count: nextType === 'None' ? '1' : prev.vehicle_count || '1',
                  }));
                }}
                className="premium-input"
              >
                <option value="None">No Parking</option>
                <option value="Car">Car Parking</option>
                <option value="Bike">Bike Parking</option>
              </select>
              {manageForm.vehicle_type !== 'None' && (
                <>
                  <label className="form-label">
                    Number of {manageForm.vehicle_type === 'Car' ? 'Cars' : 'Bikes'}
                  </label>
                  <input
                    type="number"
                    min={1}
                    step={1}
                    value={manageForm.vehicle_count}
                    onChange={(e) => setManageForm((prev) => ({ ...prev, vehicle_count: e.target.value }))}
                    className="premium-input number-spinner"
                    placeholder={`Number of ${manageForm.vehicle_type === 'Car' ? 'Cars' : 'Bikes'}`}
                  />
                  <label className="form-label">Vehicle Number</label>
                  <input
                    type="text"
                    value={manageForm.vehicle_number}
                    onChange={(e) => setManageForm((prev) => ({ ...prev, vehicle_number: e.target.value }))}
                    className="premium-input"
                    placeholder="Vehicle Number (Optional)"
                  />
                </>
              )}
              <div className="flex justify-end">
                <button
                  onClick={saveRegistrationChanges}
                  disabled={saveLoading}
                  className="gold-button disabled:opacity-60"
                >
                  {saveLoading ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </div>
          )}
        </section>

        <section className={hasInviteBackground ? 'premium-card bg-white/85 backdrop-blur-md' : 'premium-card'}>
          <h3 className="font-serif text-2xl">Announcements</h3>
          {announcements.length === 0 ? (
            <p className="mt-3 text-[var(--text-soft)]">No announcements yet.</p>
          ) : (
            <div className="mt-4 space-y-4">
              {announcements.map((item) => (
                <article key={item.id} className="rounded-2xl border border-[#C6A75E]/20 bg-[#fffdf8] p-4 shadow-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h4 className="font-semibold text-lg text-[var(--text-dark)]">{item.title}</h4>
                    <span className="text-xs text-[var(--text-soft)]">{formatAnnouncementTime(item.created_at)}</span>
                  </div>
                  <p className="mt-2 whitespace-pre-wrap text-[var(--text-dark)]">{item.message}</p>
                </article>
              ))}
            </div>
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

      {popupAnnouncement && (
        <div className="fixed right-6 top-6 z-50 w-full max-w-sm rounded-2xl border border-[#C6A75E]/35 bg-white p-4 shadow-2xl">
          <p className="text-xs uppercase tracking-wider text-[var(--text-soft)]">New Announcement</p>
          <h4 className="mt-1 font-semibold text-[var(--text-dark)]">{popupAnnouncement.title}</h4>
          <p className="mt-2 text-sm text-[var(--text-dark)]">{popupAnnouncement.message}</p>
          <p className="mt-2 text-xs text-[var(--text-soft)]">{formatAnnouncementTime(popupAnnouncement.created_at)}</p>
        </div>
      )}

      {showSosConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 px-6">
          <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-xl">
            <h4 className="font-serif text-2xl text-[var(--text-dark)]">Confirm Emergency Alert</h4>
            <p className="mt-2 text-[var(--text-soft)]">
              Are you sure you want to trigger emergency alert?
            </p>
            <div className="mt-6 flex gap-3 justify-end">
              <button
                onClick={() => {
                  setShowSosConfirm(false);
                  setSosReason('');
                }}
                className="secondary-button"
                disabled={sosSubmitting}
              >
                Cancel
              </button>
            </div>
            <label className="mt-4 block text-left text-sm text-[var(--text-soft)]" htmlFor="sos-reason">
              Reason for SOS
            </label>
            <textarea
              id="sos-reason"
              value={sosReason}
              onChange={(e) => setSosReason(e.target.value)}
              rows={4}
              maxLength={500}
              placeholder="Describe the emergency so the organizer can help quickly."
              className="mt-2 w-full rounded-xl border border-[rgba(198,167,94,0.35)] bg-[#fffdf8] px-3 py-2 text-[var(--text-dark)] focus:outline-none focus:ring-2 focus:ring-[#C6A75E]/40"
              disabled={sosSubmitting}
            />
            <p className="mt-2 text-right text-xs text-[var(--text-soft)]">{sosReason.length}/500</p>
            <button
              onClick={triggerSOS}
              disabled={sosSubmitting || !sosReason.trim()}
              className="mt-5 w-full rounded-full bg-gradient-to-r from-[#dc2626] to-[#b91c1c] px-6 py-2.5 text-white shadow-md transition-all duration-300 hover:scale-[1.01] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {sosSubmitting ? 'Sending...' : 'Trigger SOS'}
            </button>
          </div>
        </div>
      )}
    </main>
  );
}

