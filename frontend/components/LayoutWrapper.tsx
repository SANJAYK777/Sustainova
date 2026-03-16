import { ReactNode } from "react";
import Navbar from "./Navbar";

interface LayoutWrapperProps {
  children: ReactNode;
}

export default function LayoutWrapper({ children }: LayoutWrapperProps) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-[#F8F7F3] to-[#F1EFE8] section-fade">
      <Navbar />
      <main className="mx-auto w-full max-w-[1200px] px-4 py-14 sm:px-8 lg:px-10">{children}</main>
      <footer className="border-t border-[#C6A75E]/25 bg-white/80 px-4 py-6 text-center text-sm text-[var(--text-soft)]">
        Sustainova – Sustainable Event Management System
      </footer>
    </div>
  );
}

