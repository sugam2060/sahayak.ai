'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useMutation } from '@tanstack/react-query';
import { verifyEmail } from '@/services/api/auth';
import { toast } from 'sonner';
import { Loader2, CheckCircle2, XCircle } from 'lucide-react';
import { AuthBackground } from '@/components/auth/auth_login/AuthBackground';
import Image from 'next/image';

export default function VerificationPage() {
  const router = useRouter();
  const params = useParams();
  const token = params.token as string;
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');

  const { mutate, error } = useMutation({
    mutationFn: verifyEmail,
    onSuccess: (data) => {
      setStatus('success');
      toast.success(data.message);
      setTimeout(() => {
        router.push('/login');
      }, 3000);
    },
    onError: (error: Error) => {
      setStatus('error');
      toast.error(error.message);
    },
  });

  useEffect(() => {
    if (!token) {
      router.push('/login');
      return;
    }
    mutate(token);
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

        <div className="auth-card w-full animate-in fade-in slide-in-from-bottom-4 duration-500 py-12 flex flex-col items-center text-center space-y-6">
          {status === 'loading' && (
            <>
              <div className="h-20 w-20 rounded-full bg-primary/5 flex items-center justify-center">
                <Loader2 className="h-10 w-10 text-primary animate-spin" />
              </div>
              <div className="space-y-2">
                <h2 className="text-2xl font-bold text-text-primary font-heading">Verifying...</h2>
                <p className="text-sm text-muted-foreground font-sans">
                  Please wait while we verify your account.
                </p>
              </div>
            </>
          )}

          {status === 'success' && (
            <>
              <div className="h-20 w-20 rounded-full bg-green-50 flex items-center justify-center">
                <CheckCircle2 className="h-10 w-10 text-green-500" />
              </div>
              <div className="space-y-2">
                <h2 className="text-2xl font-bold text-text-primary font-heading">Verified!</h2>
                <p className="text-sm text-muted-foreground font-sans">
                  Account successfully activated. Redirecting to login...
                </p>
              </div>
            </>
          )}

          {status === 'error' && (
            <>
              <div className="h-20 w-20 rounded-full bg-red-50 flex items-center justify-center">
                <XCircle className="h-10 w-10 text-red-500" />
              </div>
              <div className="space-y-2">
                <h2 className="text-2xl font-bold text-text-primary font-heading">Verification Failed</h2>
                <p className="text-sm text-red-500 font-sans">
                  {error?.message || "Invalid or expired token."}
                </p>
              </div>
              <div className="pt-4">
                <button 
                  onClick={() => router.push('/signup')}
                  className="text-primary font-bold hover:underline"
                >
                  Try signing up again
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </main>
  );
}
