import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";
import { Sidebar } from "@/components/layout/sidebar";
import { TopBar } from "@/components/layout/top-bar";
import { ErrorBoundary } from "@/components/ui/error-boundary";

export const metadata: Metadata = {
  title: "AI Research Platform",
  description: "15-stage financial research pipeline with live tracking",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">
        <Providers>
          <div className="flex h-screen overflow-hidden">
            <Sidebar />
            <div className="flex flex-1 flex-col overflow-hidden">
              <TopBar />
              <main className="flex-1 overflow-auto p-6">
                <ErrorBoundary>
                  {children}
                </ErrorBoundary>
              </main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
