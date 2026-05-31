import { Suspense } from "react";
import { Header } from "@/components/Header";
import { Sidebar } from "@/components/Sidebar";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="flex flex-col min-h-screen bg-zinc-50 dark:bg-black">
      <Header />
      <div className="flex flex-1">
        <Suspense fallback={<aside className="w-16 bg-white dark:bg-zinc-900 border-r border-zinc-200 dark:border-zinc-800 h-[calc(100vh-64px)]" />}>
          <Sidebar />
        </Suspense>
        <main className="flex-1 p-2 md:px-4 md:py-8 overflow-y-auto h-[calc(100vh-64px)]">
          <Suspense fallback={
            <div className="min-h-[50vh] flex flex-col items-center justify-center p-6">
              <div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
            </div>
          }>
            {children}
          </Suspense>
        </main>
      </div>
    </div>
  );
}
