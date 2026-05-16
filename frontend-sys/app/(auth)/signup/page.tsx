import { Metadata } from 'next';
import Image from 'next/image';
import { SignupFlow } from '@/components/auth/auth_signup/SignupFlow';
import { AuthBackground } from '@/components/auth/auth_login/AuthBackground';

export const metadata: Metadata = {
  title: 'Signup — Sahayak AI',
  description: 'Create your Sahayak AI workspace and start managing your social commerce efficiently.',
};

export default function SignupPage() {
  return (
    <main className="relative min-h-screen w-full flex flex-col items-center justify-center p-4 md:p-8 overflow-hidden">
      <AuthBackground />
      
      <div className="z-10 w-full max-w-md flex flex-col items-center space-y-6">
        {/* Brand Mark */}
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

        {/* Signup Multi-step Flow */}
        <SignupFlow />
      </div>

      {/* Background Gradients for extra depth */}
      <div className="fixed top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-primary/5 blur-[120px] pointer-events-none -z-5" />
      <div className="fixed bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-blue-500/5 blur-[120px] pointer-events-none -z-5" />
    </main>
  );
}
