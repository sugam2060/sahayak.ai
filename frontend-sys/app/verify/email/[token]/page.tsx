'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useConfirmEmailChange } from '@/services/api/account';
import { toast } from 'sonner';
import { Loader2, CheckCircle2, XCircle } from 'lucide-react';
import { AuthBackground } from '@/components/auth/auth_login/AuthBackground';
import Image from 'next/image';

export default function EmailVerificationPage() {
  const router = useRouter();
  const params = useParams();
  const token = params.token as string;
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');

  const { mutate, error } = useConfirmEmailChange();

  useEffect(() => {
    if (!token) {
      router.push('/');
      return;
    }
    mutate(token, {
      onSuccess: (data) => {
        setStatus('success');
        toast.success(data.message || 'Email verified and updated successfully.');
        setTimeout(() => {
          router.push('/');
        }, 3000);
      },
      onError: (err: Error) => {
        setStatus('error');
        toast.error(err.message || 'Verification failed. The link may have expired.');
      },
    });
  }, [token, router, mutate]);

  return (
    <main className="relative min-h-screen w-full flex flex-col items-center justify-center p-4 md:p-8 overflow-hidden">
      <AuthBackground />
      
      <div className="z-10 w-full max-w-md flex flex-col items-center space-y-6">
        <div className="flex flex-col items-center">
          <Image
            src="/logo.png"
            alt="Sahayak AI Logo"
            width={200}
            height={60}
            priority
            className="h-28 scale-150 w-auto object-contain"
          />
        </div>

        <div className="auth-card w-full animate-in fade-in slide-in-from-bottom-4 duration-500 py-12 flex flex-col items-center text-center space-y-6 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl p-6 shadow-2xl">
          {status === 'loading' && (
            <>
              <div className="h-20 w-20 rounded-full bg-primary/5 flex items-center justify-center animate-pulse">
                <Loader2 className="h-10 w-10 text-primary animate-spin" />
              </div>
              <div className="space-y-2">
                <h2 className="text-2xl font-bold text-zinc-900 dark:text-white font-heading">Confirming Email Change...</h2>
                <p className="text-sm text-zinc-500 dark:text-zinc-400 font-sans">
                  Please wait while we verify your new email address.
                </p>
              </div>
            </>
          )}

          {status === 'success' && (
            <>
              <div className="h-20 w-20 rounded-full bg-emerald-50 dark:bg-emerald-950/20 flex items-center justify-center">
                <CheckCircle2 className="h-10 w-10 text-emerald-500" />
              </div>
              <div className="space-y-2">
                <h2 className="text-2xl font-bold text-zinc-900 dark:text-white font-heading">Email Verified!</h2>
                <p className="text-sm text-zinc-500 dark:text-zinc-400 font-sans">
                  Your email has been successfully updated. Redirecting to home...
                </p>
              </div>
            </>
          )}

          {status === 'error' && (
            <>
              <div className="h-20 w-20 rounded-full bg-red-50 dark:bg-red-950/20 flex items-center justify-center">
                <XCircle className="h-10 w-10 text-red-500" />
              </div>
              <div className="space-y-2">
                <h2 className="text-2xl font-bold text-zinc-900 dark:text-white font-heading">Verification Failed</h2>
                <p className="text-sm text-red-500 font-sans px-4">
                  {error?.message || "This verification link is invalid or has expired."}
                </p>
              </div>
              <div className="pt-4">
                <button 
                  onClick={() => router.push('/')}
                  className="text-primary font-bold hover:underline"
                >
                  Go back to Dashboard
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </main>
  );
}
