"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

export default function Navbar() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 backdrop-blur-md bg-[#0B0F14]/95 border-b border-[#C6A75E]/35">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <Link href="/" className="inline-flex items-center" aria-label="Eventify Home">
          <Image
            src="/logo-navbar.png"
            alt="Eventify"
            width={980}
            height={700}
            quality={100}
            priority
            className="h-14 w-auto sm:h-16"
          />
        </Link>

        <div className="hidden md:flex items-center gap-6">
          <Link
            href="/login"
            className="rounded-full px-6 py-2.5 text-white
                       bg-gradient-to-r from-[#C6A75E] to-[#A88B4C]
                       shadow-md hover:shadow-lg
                       hover:scale-105 transition-all duration-300"
          >
            Login
          </Link>

          <Link
            href="/register"
            className="rounded-full px-6 py-2.5 text-white
                       bg-gradient-to-r from-[#1F4F46] to-[#163E38]
                       shadow-md hover:shadow-lg
                       hover:scale-105 transition-all duration-300"
          >
            Organizer Register
          </Link>
        </div>

        <button
          className="md:hidden text-[#C6A75E]"
          onClick={() => setOpen(!open)}
          aria-label={open ? "Close menu" : "Open menu"}
        >
          <span className="inline-flex h-8 w-8 items-center justify-center text-2xl leading-none">
            {open ? "x" : "="}
          </span>
        </button>
      </div>

      {open && (
        <div className="md:hidden px-6 pb-6 space-y-4 bg-[#0B0F14]/95 backdrop-blur-md">
          <Link
            href="/login"
            onClick={() => setOpen(false)}
            className="block w-full text-center rounded-full px-6 py-3 text-white
                       bg-gradient-to-r from-[#C6A75E] to-[#A88B4C]
                       shadow-md hover:scale-105 transition-all duration-300"
          >
            Login
          </Link>

          <Link
            href="/register"
            onClick={() => setOpen(false)}
            className="block w-full text-center rounded-full px-6 py-3 text-white
                       bg-gradient-to-r from-[#1F4F46] to-[#163E38]
                       shadow-md hover:scale-105 transition-all duration-300"
          >
            Organizer Register
          </Link>
        </div>
      )}
    </header>
  );
}
