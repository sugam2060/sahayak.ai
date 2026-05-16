import { Metadata } from 'next';
import Image from 'next/image';
import { LoginForm } from '@/components/auth/auth_login/LoginForm';
import { AuthBackground } from '@/components/auth/auth_login/AuthBackground';

export const metadata: Metadata = {
  title: 'Login | Sahayak AI',
  description: 'Sign in to your Sahayak AI workspace',
};

export default function LoginPage() {
  return (
    <main className="relative min-h-screen flex items-center justify-center p-6">
      <AuthBackground />
      
      <div className="z-10 w-full max-w-md flex flex-col items-center space-y-8">
        {/* Brand Mark */}
        <div className="flex flex-col items-center mb-4">
          <Image
            src="/logo.png"
            alt="Sahayak AI Logo"
            width={200}
            height={60}
            priority
            className="h-28 scale-150 w-auto object-contain"
          />
        </div>

        {/* Form Container */}
        <LoginForm />

        {/* Simple Footer Link */}
        <p className="text-xs text-text-tertiary font-ui uppercase tracking-widest text-center">
          Powered by Advanced Agentic Intelligence
        </p>
      </div>
    </main>
  );
}
