'use client';

import { AxiosError } from 'axios';
import { useParams } from 'next/navigation';
import { ChangeEvent, useState } from 'react';
import LuxurySelect from '../../../components/LuxurySelect';
import api from '../../../services/api';
import { formatPhoneForInput, normalizePhone } from '../../../services/phone';

export default function GuestPage() {
  const params = useParams();
  const eventToken = params.eventToken as string;

  const [form, setForm] = useState({
    name: '',
    phone: '',
    number_of_people: 1,
    coming_from: '',
    transport_type: '',
    parking_type: 'None',
    vehicle_number: '',
    needs_room: 'No',
    aadhar_number: '',
    room_type: '',
  });

  const [status, setStatus] = useState('');
  const [guestQrCodeUrl, setGuestQrCodeUrl] = useState('');

  const handleChange = (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]:
        name === 'number_of_people'
          ? Number(value)
          : name === 'aadhar_number'
            ? value.replace(/\D/g, '').slice(0, 12)
          : name === 'phone'
            ? formatPhoneForInput(value)
            : value,
    }));
  };

  const setSelectValue = (name: 'transport_type' | 'parking_type' | 'needs_room', value: string) => {
    setForm((prev) => {
      if (name === 'parking_type' && value === 'None') {
        return { ...prev, [name]: value, vehicle_number: '' };
      }
      if (name === 'needs_room' && value === 'No') {
        return { ...prev, [name]: value, aadhar_number: '', room_type: '' };
      }
      return { ...prev, [name]: value };
    });
  };

  const submit = async (e: any) => {
    e.preventDefault();

    if (!form.transport_type) {
      setStatus('Please select transport type');
      return;
    }

    try {
      const res = await api.post('/guests/rsvp', {
        ...form,
        parking_type: form.parking_type,
        phone: normalizePhone(form.phone),
        event_token: eventToken,
      });

      setGuestQrCodeUrl(res.data?.guest_qr_code_url || '');

      setStatus('RSVP submitted successfully');
      setForm({
        name: '',
        phone: '',
        number_of_people: 1,
        coming_from: '',
        transport_type: '',
        parking_type: 'None',
        vehicle_number: '',
        needs_room: 'No',
        aadhar_number: '',
        room_type: '',
      });
    } catch (err: unknown) {
      const apiErr = err as AxiosError<{ detail?: string }>;
      setStatus(apiErr.response?.data?.detail || 'Something went wrong');
    }
  };

  return (
    <main className="min-h-[80vh] flex items-center justify-center px-6 py-8">
      <section className="premium-card hover:-translate-y-2 transition-all duration-300 w-full max-w-2xl text-center">
        <h1 className="font-serif text-5xl">Event RSVP</h1>
        <div className="h-px w-40 bg-gradient-to-r from-transparent via-[#C6A75E] to-transparent mx-auto my-6" />

        <form onSubmit={submit} className="space-y-4 text-left">
          <input name="name" value={form.name} placeholder="Your Name" required onChange={handleChange} className="premium-input" />
          <input name="phone" value={form.phone} placeholder="Phone Number" required onChange={handleChange} inputMode="numeric" maxLength={11} className="premium-input" />
          <input name="number_of_people" type="number" min={1} value={form.number_of_people} placeholder="Total Members" required onChange={handleChange} className="premium-input" />
          <input
            name="coming_from"
            value={form.coming_from}
            placeholder="Enter the city or location you are coming from"
            onChange={handleChange}
            className="premium-input"
          />

          <LuxurySelect
            value={form.transport_type}
            options={['Bike', 'Car', 'Public Transport']}
            placeholder="Transport Type"
            onChange={(value: string) => setSelectValue('transport_type', value)}
          />

          <p className="text-sm text-[var(--text-soft)]">
            For better event arrangements, please let us know your parking and accommodation needs.
          </p>

          <div className="space-y-2">
            <h3 className="font-semibold text-lg text-[#1F4F46]">Parking Requirement</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {[
                { value: 'Car', label: 'Car Parking' },
                { value: 'Bike', label: 'Bike Parking' },
                { value: 'None', label: 'No Parking Required' },
              ].map((option) => (
                <label
                  key={option.value}
                  className={`border rounded-2xl p-4 cursor-pointer hover:border-[#C6A75E] transition-all ${
                    form.parking_type === option.value
                      ? 'border-[#C6A75E] bg-[#C6A75E]/10'
                      : 'border-gray-200 bg-white'
                  }`}
                >
                  <input
                    type="radio"
                    name="parking_type"
                    value={option.value}
                    checked={form.parking_type === option.value}
                    onChange={(e) => setSelectValue('parking_type', e.target.value)}
                    className="sr-only"
                  />
                  <span className="text-sm text-[var(--text-dark)]">{option.label}</span>
                </label>
              ))}
            </div>
          </div>

          {form.parking_type !== 'None' && (
            <input
              name="vehicle_number"
              value={form.vehicle_number}
              placeholder="Enter Vehicle Number (e.g., TN10AB1234)"
              onChange={handleChange}
              className="premium-input"
            />
          )}

          <div className="space-y-2">
            <h3 className="font-semibold text-lg text-[#1F4F46]">Do you need accommodation (room)?</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {[
                { value: 'Yes', label: 'Yes, I need a room' },
                { value: 'No', label: 'No room required' },
              ].map((option) => (
                <label
                  key={option.value}
                  className={`border rounded-2xl p-4 cursor-pointer hover:border-[#C6A75E] transition-all ${
                    form.needs_room === option.value
                      ? 'border-[#C6A75E] bg-[#C6A75E]/10'
                      : 'border-gray-200 bg-white'
                  }`}
                >
                  <input
                    type="radio"
                    name="needs_room"
                    value={option.value}
                    checked={form.needs_room === option.value}
                    onChange={(e) => setSelectValue('needs_room', e.target.value)}
                    className="sr-only"
                  />
                  <span className="text-sm text-[var(--text-dark)]">{option.label}</span>
                </label>
              ))}
            </div>
          </div>

          {form.needs_room === 'Yes' && (
            <div className="space-y-4">
              <input
                name="aadhar_number"
                value={form.aadhar_number}
                placeholder="Enter Aadhar Number"
                onChange={handleChange}
                inputMode="numeric"
                maxLength={12}
                className="premium-input"
              />
              <select
                name="room_type"
                value={form.room_type}
                onChange={handleChange}
                className="premium-input"
              >
                <option value="">Select Room Type</option>
                <option value="Single Bed">Single Bed</option>
                <option value="Double Bed">Double Bed</option>
                <option value="Triple Bed">Triple Bed</option>
              </select>
            </div>
          )}

          <button className="gold-button w-full">Submit RSVP</button>
        </form>

        {status && <p className="mt-4 text-center text-[var(--emerald)]">{status}</p>}
        {guestQrCodeUrl && (
          <div className="mt-6 rounded-2xl border border-[#C6A75E]/30 bg-[#fffdf8] p-4">
            <p className="text-sm text-[var(--text-soft)] mb-3">
              Save this QR for entrance check-in.
            </p>
            <img
              src={guestQrCodeUrl}
              alt="Guest check-in QR"
              className="mx-auto h-48 w-48 rounded-xl border border-[#C6A75E]/30 bg-white p-2"
            />
          </div>
        )}
      </section>
    </main>
  );
}

