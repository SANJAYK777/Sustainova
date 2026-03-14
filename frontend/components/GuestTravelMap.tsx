'use client';

import {
  BubbleController,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  PointElement,
  Tooltip,
} from 'chart.js';
import { Bubble } from 'react-chartjs-2';

interface TravelPoint {
  city: string;
  guests: number;
  lat: number;
  lng: number;
}

interface GuestTravelMapProps {
  points: TravelPoint[];
}

ChartJS.register(BubbleController, CategoryScale, LinearScale, PointElement, Tooltip, Legend);

function markerRadius(guests: number): number {
  if (guests >= 100) return 18;
  if (guests >= 50) return 14;
  if (guests >= 20) return 11;
  if (guests >= 5) return 8;
  return 6;
}

export default function GuestTravelMap({ points }: GuestTravelMapProps) {
  const bubbleData = points.map((point) => ({
    x: point.lng,
    y: point.lat,
    r: markerRadius(point.guests),
    city: point.city,
    guests: point.guests,
  }));

  return (
    <div className="h-[420px] w-full rounded-2xl border border-[#C6A75E]/20 bg-[#fffdf8] p-3 shadow-md">
      <Bubble
        data={{
          datasets: [
            {
              label: 'Guest Origin',
              data: bubbleData,
              backgroundColor: 'rgba(31,79,70,0.65)',
              borderColor: '#ffffff',
              borderWidth: 1.2,
            },
          ],
        }}
        options={{
          maintainAspectRatio: false,
          scales: {
            x: {
              min: 68,
              max: 92,
              title: { display: true, text: 'Longitude' },
              grid: { color: 'rgba(198,167,94,0.15)' },
            },
            y: {
              min: 6,
              max: 38,
              title: { display: true, text: 'Latitude' },
              grid: { color: 'rgba(198,167,94,0.15)' },
            },
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                title: (items) => String((items[0].raw as any)?.city || ''),
                label: (item) => `Guests: ${String((item.raw as any)?.guests || 0)}`,
              },
            },
          },
        }}
      />
    </div>
  );
}
