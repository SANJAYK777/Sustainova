'use client';

import { useEffect, useState } from 'react';
import api from '../../../services/api';

type CheckinResponse = {
  status: string;
  message: string;
  guest_name: string;
  scanned_at: string;
  checked_in_guests: number;
  remaining_guests: number;
  real_present_count: number;
};

export default function GuestCheckinPage({ params }: { params: { guestQrToken: string } }) {
  const [result, setResult] = useState<CheckinResponse | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await api.get<CheckinResponse>(`/checkin/${params.guestQrToken}`);
        setResult(res.data);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Unable to process check-in');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [params.guestQrToken]);

  if (loading) {
    return <p className="py-16 text-center text-[var(--text-soft)]">Processing check-in...</p>;
  }

  return (
    <main className="min-h-[80vh] px-6 py-12">
      <section className="premium-card mx-auto max-w-xl text-center">
        {error ? (
          <>
            <h1 className="font-serif text-4xl text-red-700">Check-In Failed</h1>
            <p className="mt-4 text-[var(--text-soft)]">{error}</p>
          </>
        ) : (
          <>
            <h1 className="font-serif text-4xl text-[var(--primary)]">{result?.message}</h1>
            <p className="mt-3 text-[var(--text-dark)]">Guest: {result?.guest_name}</p>
            <div className="mt-6 space-y-1 text-[var(--text-soft)]">
              <p>Checked-in guests: {result?.checked_in_guests}</p>
              <p>Remaining guests: {result?.remaining_guests}</p>
              <p>Real present count: {result?.real_present_count}</p>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
