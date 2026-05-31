import React from 'react';
import Link from 'next/link';

export default function LegalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-bg-canvas flex flex-col items-center py-12 px-4">
      <div className="mb-12 text-center">
        <Link href="/" className="inline-flex items-center gap-2 mb-4">
          <div className="w-10 h-10 rounded-xl bg-linear-to-br from-[#7C63D4] to-[#5E9EEB] flex items-center justify-center text-white shadow-lg">
             <span className="text-xl font-black italic">S</span>
          </div>
          <span className="text-2xl font-black text-[#1E1B4B] tracking-tight">Sahayak AI</span>
        </Link>
      </div>
      
      <div className="w-full max-w-4xl bg-white/70 backdrop-blur-2xl border border-white/50 rounded-[32px] shadow-2xl shadow-indigo-100/50 p-8 md:p-12 overflow-hidden relative">
        <div className="absolute top-0 left-0 w-full h-2 bg-linear-to-r from-[#7C63D4] via-[#5E9EEB] to-[#7C63D4]" />
        {children}
      </div>

      <div className="mt-8 text-center">
        <p className="text-slate-400 text-xs font-medium uppercase tracking-[0.2em]">
          © 2026 Sahayak AI • Built for Modern Business
        </p>
      </div>
    </div>
  );
}
