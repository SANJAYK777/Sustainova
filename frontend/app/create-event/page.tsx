'use client';

import { AxiosError } from 'axios';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import api from '../../services/api';
import { useToast } from '../../components/ToastContext';

type CreateEventForm = {
  event_name: string;
  location: string;
  event_date: string;
  expected_count: string;
  invitation_image_url: string;
};

type EventResponse = {
  id: number;
  event_token: string;
  qr_code_url: string;
};

type ApiError = {
  detail?: string;
};

export default function CreateEvent() {
  const router = useRouter();
  const { showToast } = useToast();

  const [form, setForm] = useState<CreateEventForm>({
    event_name: '',
    location: '',
    event_date: '',
    expected_count: '',
    invitation_image_url: '',
  });

  const [qr, setQr] = useState('');
  const [eventId, setEventId] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      router.replace('/login');
    }
  }, [router]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      setForm((prev) => ({ ...prev, invitation_image_url: reader.result as string }));
    };
    reader.readAsDataURL(file);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const res = await api.post<EventResponse>('/events/', {
        ...form,
        expected_count: parseInt(form.expected_count, 10) || 0,
      });

      setQr(res.data.qr_code_url);
      setEventId(`EVT-${new Date().getFullYear()}-${res.data.id}`);
      showToast('Event created successfully', 'success');
    } catch (err) {
      const apiErr = err as AxiosError<ApiError>;
      setError(apiErr.response?.data?.detail || 'Unable to create event.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-[80vh] flex items-center justify-center px-6 py-8">
      <section className="premium-card hover:-translate-y-2 transition-all duration-300 w-full max-w-3xl">
        <div className="text-center mb-8">
          <h1 className="font-serif text-5xl">Create Your Event</h1>
          <div className="h-px w-40 bg-gradient-to-r from-transparent via-[#C6A75E] to-transparent mx-auto my-6" />
          <p className="text-[var(--text-soft)]">Craft your event details and generate your premium invitation QR.</p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <input name="event_name" value={form.event_name} onChange={handleChange} required className="premium-input" placeholder="Event Name" />
          <input name="location" value={form.location} onChange={handleChange} required className="premium-input" placeholder="Location" />

          <div className="grid md:grid-cols-2 gap-4">
            <input type="datetime-local" name="event_date" value={form.event_date} onChange={handleChange} required className="premium-input" />
            <input type="number" name="expected_count" value={form.expected_count} onChange={handleChange} required className="premium-input" placeholder="Expected Guests" />
          </div>

          <input type="file" accept="image/*" onChange={handleFile} className="premium-input" />

          {error && <p className="text-red-600 text-sm">{error}</p>}

          <button type="submit" disabled={loading} className="gold-button w-full disabled:opacity-60">
            {loading ? 'Creating...' : 'Create Event'}
          </button>
        </form>

        {qr && (
          <div className="mt-10 text-center border-t border-[rgba(198,167,94,0.2)] pt-8">
            <h2 className="font-serif text-3xl mb-3">Your Invitation QR</h2>
            <p className="text-sm text-[var(--text-soft)] mb-5">Event ID: <span className="font-semibold">{eventId}</span></p>
            <img src={qr} alt="Event QR" className="h-56 w-56 rounded-3xl border border-[rgba(198,167,94,0.25)] mx-auto" />
          </div>
        )}
      </section>
    </main>
  );
}

