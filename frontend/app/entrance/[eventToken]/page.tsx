'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import api from '../../../services/api';

type CheckinResponse = {
  status: string;
  message: string;
  guest_id: number;
  guest_name: string;
  event_id: number;
  scanned_at: string;
  checked_in_guests: number;
  remaining_guests: number;
  real_present_count: number;
};

function parseGuestQrToken(raw: string): string | null {
  const value = (raw || '').trim();
  if (!value) return null;

  if (value.startsWith('/checkin/')) {
    return value.split('/checkin/')[1]?.split(/[?#]/)[0] || null;
  }

  try {
    const url = new URL(value);
    const match = url.pathname.match(/^\/checkin\/([^/]+)$/);
    if (match?.[1]) return match[1];
  } catch {
    // no-op
  }

  return null;
}

export default function EntrancePage({ params }: { params: { eventToken: string } }) {
  const [event, setEvent] = useState<any>(null);
  const [status, setStatus] = useState('');
  const [checkinResult, setCheckinResult] = useState<CheckinResponse | null>(null);
  const [cameraEnabled, setCameraEnabled] = useState(false);
  const [manualQr, setManualQr] = useState('');
  const [scanError, setScanError] = useState('');
  const [processing, setProcessing] = useState(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const scanLoopRef = useRef<number | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const lastTokenRef = useRef<string>('');
  const coolDownRef = useRef<number>(0);

  useEffect(() => {
    api
      .get(`/events/token/${params.eventToken}`)
      .then((res) => setEvent(res.data))
      .catch(() => setStatus('Event not found'));
  }, [params.eventToken]);

  const supportsBarcodeDetector = useMemo(
    () => typeof window !== 'undefined' && 'BarcodeDetector' in window,
    []
  );

  const stopCamera = () => {
    if (scanLoopRef.current) cancelAnimationFrame(scanLoopRef.current);
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    scanLoopRef.current = null;
  };

  const submitToken = async (token: string) => {
    if (!token || processing) return;

    setProcessing(true);
    setScanError('');
    try {
      const res = await api.get<CheckinResponse>(`/checkin/${token}`);
      if (event && res.data.event_id !== event.id) {
        setScanError('This guest QR belongs to a different event.');
        return;
      }

      setCheckinResult(res.data);
      setStatus(`${res.data.message}: ${res.data.guest_name}`);
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Unable to process check-in';
      setScanError(msg);
      setStatus(msg);
    } finally {
      setProcessing(false);
    }
  };

  useEffect(() => {
    if (!cameraEnabled || !supportsBarcodeDetector) return;

    let mounted = true;

    const start = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' } },
          audio: false,
        });

        if (!mounted || !videoRef.current) return;

        streamRef.current = stream;
        videoRef.current.srcObject = stream;
        await videoRef.current.play();

        const BarcodeDetectorImpl = (window as any).BarcodeDetector;
        const detector = new BarcodeDetectorImpl({ formats: ['qr_code'] });

        const detectFrame = async () => {
          if (!videoRef.current) return;
          try {
            const barcodes = await detector.detect(videoRef.current);
            if (barcodes?.length) {
              const raw = barcodes[0].rawValue || '';
              const token = parseGuestQrToken(raw);
              const now = Date.now();

              if (token && (lastTokenRef.current !== token || now - coolDownRef.current > 2500)) {
                lastTokenRef.current = token;
                coolDownRef.current = now;
                submitToken(token);
              }
            }
          } catch {
            // no-op
          }

          scanLoopRef.current = requestAnimationFrame(detectFrame);
        };

        scanLoopRef.current = requestAnimationFrame(detectFrame);
      } catch {
        setScanError('Unable to access camera. Allow camera permissions and retry.');
        setCameraEnabled(false);
      }
    };

    start();
    return () => {
      mounted = false;
      stopCamera();
    };
  }, [cameraEnabled, supportsBarcodeDetector]);

  useEffect(() => () => stopCamera(), []);

  const manualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = parseGuestQrToken(manualQr);
    if (!token) {
      setScanError('Invalid QR value. Expected /checkin/{guest_qr_token}');
      return;
    }
    await submitToken(token);
  };

  if (!event && !status) return <p className="text-center text-[var(--text-soft)] py-16">Loading...</p>;
  if (!event) return <p className="text-center text-red-700 py-16">{status}</p>;

  return (
    <main className="min-h-[80vh] px-6 py-8">
      <section className="premium-card mx-auto w-full max-w-3xl space-y-6">
        <div className="text-center">
          <h1 className="font-serif text-4xl">Entrance Check-In</h1>
          <p className="mt-2 text-[var(--text-soft)]">{event.event_name}</p>
        </div>

        <div className="space-y-4 rounded-2xl border border-[#C6A75E]/25 bg-[#fffdf8] p-4">
          <div className="flex flex-wrap items-center gap-3">
            <button
              className="gold-button"
              onClick={() => setCameraEnabled((prev) => !prev)}
              disabled={!supportsBarcodeDetector}
            >
              {cameraEnabled ? 'Stop Scanner' : 'Start Camera Scanner'}
            </button>
            {!supportsBarcodeDetector && (
              <p className="text-sm text-red-700">QR camera scanning is not supported on this browser.</p>
            )}
          </div>

          <div className="overflow-hidden rounded-xl border border-[#C6A75E]/20 bg-black">
            <video ref={videoRef} className="h-72 w-full object-cover" muted playsInline />
          </div>

          <form onSubmit={manualSubmit} className="space-y-3">
            <label className="text-sm text-[var(--text-soft)]">Manual fallback (paste QR URL/value)</label>
            <input
              value={manualQr}
              onChange={(e) => setManualQr(e.target.value)}
              placeholder="https://.../checkin/{guest_qr_token}"
              className="premium-input"
            />
            <button className="secondary-button" type="submit" disabled={processing}>
              {processing ? 'Processing...' : 'Check In'}
            </button>
          </form>
        </div>

        {status && <p className="text-center text-[var(--emerald)]">{status}</p>}
        {scanError && <p className="text-center text-red-700">{scanError}</p>}

        {checkinResult && (
          <div className="rounded-2xl border border-[#C6A75E]/25 bg-white p-5">
            <p className="font-semibold text-[var(--text-dark)]">Guest: {checkinResult.guest_name}</p>
            <p className="mt-1 text-[var(--text-soft)]">Checked-in guests: {checkinResult.checked_in_guests}</p>
            <p className="text-[var(--text-soft)]">Remaining guests: {checkinResult.remaining_guests}</p>
            <p className="text-[var(--text-soft)]">Real present count: {checkinResult.real_present_count}</p>
          </div>
        )}
      </section>
    </main>
  );
}
