import Link from "next/link";
import Image from "next/image";

export default function Home() {
  return (
    <section className="section-fade relative overflow-hidden py-20">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_top,rgba(198,167,94,0.25),transparent_58%)]" />

      <div className="mx-auto max-w-7xl px-6 sm:px-10">
        <div className="premium-card border border-[#C6A75E]/25 bg-white/85 text-center">
          <Image
            src="/Sustainova_logo.jpeg"
            alt="Sustainova logo"
            width={220}
            height={220}
            priority
            className="mx-auto h-24 w-auto sm:h-28"
          />
          <p className="text-sm uppercase tracking-[0.25em] text-[var(--text-soft)]">Sustainova</p>
          <h1 className="mx-auto mt-6 max-w-4xl font-serif text-5xl leading-tight text-[var(--text-dark)] sm:text-6xl">
            Sustainova – Sustainable Event Management System
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-[var(--text-soft)]">
            Elegant planning for modern events with guest logistics, SOS alerts, invitation workflows, and smart organization in one platform.
          </p>

          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row sm:gap-6">
            <Link href="/register" className="gold-button inline-flex min-w-[220px] items-center justify-center">
              Organizer Register
            </Link>
            <Link href="/login" className="secondary-button inline-flex min-w-[220px] items-center justify-center">
              Guest Login
            </Link>
          </div>
        </div>

        <div className="mt-10 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {[
            {
              title: 'Smart RSVP Experience',
              desc: 'Collect guest details, parking preference, and room needs in a polished RSVP flow.',
              icon: 'RS',
            },
            {
              title: 'Live SOS Alerting',
              desc: 'Guests can trigger SOS alerts while organizers receive real-time dashboard visibility.',
              icon: 'SO',
            },
            {
              title: 'Elegant Planning Insights',
              desc: 'Track attendance, transport, and safety-buffer metrics with premium dashboard views.',
              icon: 'IN',
            },
          ].map((feature) => (
            <article key={feature.title} className="premium-card bg-white">
              <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-[#1F4F46]/10 text-sm font-bold text-[#1F4F46]">
                {feature.icon}
              </span>
              <h3 className="mt-4 text-xl font-semibold">{feature.title}</h3>
              <p className="mt-2 text-[var(--text-soft)]">{feature.desc}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

