'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import Image from 'next/image';
import api from '../../services/api';
import { useToast } from '../../components/ToastContext';
import { formatPhoneForInput, normalizePhone } from '../../services/phone';

export default function LoginPage() {
  const router = useRouter();
  const { showToast } = useToast();

  const [phone, setPhone] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const phoneClean = normalizePhone(phone);
      await api.post('/auth/request-otp', { phone: phoneClean });

      showToast('OTP sent to your phone.', 'success');
      router.push(`/verify-otp?phone=${phoneClean}`);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to send OTP';
      setError(errorMsg);
      showToast(errorMsg, 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-[80vh] flex items-center justify-center px-4">
      <section className="premium-card hover:-translate-y-2 transition-all duration-300 w-full max-w-xl text-center">
        <Image
          src="/Sustainova_logo.jpeg"
          alt="Sustainova logo"
          width={180}
          height={180}
          priority
          className="mx-auto h-20 w-auto"
        />
        <h1 className="font-serif text-5xl">Cherish Your Celebration</h1>
        <div className="h-px w-40 bg-gradient-to-r from-transparent via-[#C6A75E] to-transparent mx-auto my-6" />
        <p className="text-[var(--text-soft)] mb-8">Sign in with OTP to continue managing your event moments.</p>

        <form onSubmit={submit} className="form-stack text-left">
          <label className="form-label" htmlFor="phone-input">Mobile Number</label>
          <input
            id="phone-input"
            type="tel"
            placeholder="Enter mobile number"
            value={phone}
            onChange={(e) => setPhone(formatPhoneForInput(e.target.value))}
            inputMode="numeric"
            maxLength={11}
            required
            className="premium-input"
          />

          {error && <p className="text-red-600 text-sm">{error}</p>}

          <button type="submit" disabled={loading} className="gold-button w-full disabled:opacity-60">
            {loading ? 'Sending OTP...' : 'Send OTP'}
          </button>
        </form>

        <p className="text-sm text-[var(--text-soft)] mt-7">
          Don&apos;t have an account?{' '}
          <a href="/register" className="text-[var(--gold-dark)] font-semibold">
            Register here
          </a>
        </p>
      </section>
    </main>
  );
}

