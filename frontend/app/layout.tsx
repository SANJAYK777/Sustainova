import type { Metadata } from "next";
import "../styles/globals.css";
import LayoutWrapper from "../components/LayoutWrapper";
import { ToastProvider } from "../components/ToastContext";
import { AuthProvider } from "../context/AuthContext";

export const metadata: Metadata = {
  title: "Eventify",
  description: "Sustainability Meets Celebration",
  icons: {
    icon: "/favicon.ico",
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
