import type { Metadata } from "next";
import "../styles/globals.css";
import LayoutWrapper from "../components/LayoutWrapper";
import { ToastProvider } from "../components/ToastContext";
import { AuthProvider } from "../context/AuthContext";

export const metadata: Metadata = {
  title: "Sustainova – Sustainable Event Management System",
  description: "Sustainova – Sustainable Event Management System",
  icons: {
    icon: "/favicon.ico",
    shortcut: "/favicon.ico",
    apple: "/favicon.ico",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">
        <AuthProvider>
          <ToastProvider>
            <LayoutWrapper>{children}</LayoutWrapper>
          </ToastProvider>
        </AuthProvider>
      </body>
    </html>
  );
}

