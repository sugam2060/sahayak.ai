'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useMutation } from '@tanstack/react-query';
import { SignupFormOrgDetail } from './SignupFormOrgDetail';
import { SignupFormUserDetail } from './SignupFormUserDetail';
import { SignupProgress } from './SignupProgress';
import { SignupData } from '@/types/auth';
import { registerUser } from '@/services/api/auth';
import { CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

export const SignupFlow = () => {
  const [step, setStep] = useState(0);
  const [formData, setFormData] = useState<Partial<SignupData>>({});
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: registerUser,
    onSuccess: (data) => {
      setSuccessMessage(data.message);
      toast.success(data.message);
    },
    onError: (error: Error) => {
      toast.error(error.message);
    }
  });

  const generateSlug = (name: string) => {
    const base = name.toLowerCase()
      .replace(/[^a-z0-9]/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '');
    const timestamp = Date.now().toString(36);
    const random = Math.random().toString(36).substring(2, 5);
    return `${base}-${timestamp}-${random}`;
  };

  const handleNext = (data: { organizationName: string }) => {
    const slug = generateSlug(data.organizationName);
    setFormData((prev) => ({ ...prev, ...data, organizationSlug: slug }));
    setStep(1);
  };

  const handleBack = () => {
    setStep(0);
  };

  const handleSubmit = async (data: Pick<SignupData, 'fullName' | 'email' | 'password' | 'confirmPassword'>) => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { confirmPassword, ...userDetails } = data;
    const finalData = { ...formData, ...userDetails } as SignupData;
    try {
      await mutation.mutateAsync(finalData);
    } catch {
      // Error is already handled by mutation.onError
    }
  };

  const steps = ['Workspace', 'Account'];

  if (successMessage) {
    return (
      <div className="auth-card w-full animate-in fade-in zoom-in duration-500 py-12 flex flex-col items-center text-center space-y-6">
        <div className="h-20 w-20 rounded-full bg-green-50 flex items-center justify-center">
          <CheckCircle2 className="h-10 w-10 text-green-500" />
        </div>
        <div className="space-y-2">
          <h2 className="text-2xl font-bold text-text-primary font-heading">Verify your email</h2>
          <p className="text-sm text-muted-foreground font-sans max-w-[280px] mx-auto">
            {successMessage}
          </p>
        </div>
        <div className="pt-4">
          <Link href="/login">
            <Button variant="outline" className="rounded-xl px-8 h-11 border-border bg-white/50">
              Go to Login
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center w-full max-w-md mx-auto">
      <SignupProgress currentStep={step} steps={steps} />
      
      {step === 0 ? (
        <SignupFormOrgDetail 
          onNext={handleNext} 
          defaultValues={{ organizationName: formData.organizationName }} 
        />
      ) : (
        <SignupFormUserDetail 
          onBack={handleBack} 
          onSubmit={handleSubmit} 
          orgName={formData.organizationName || 'Your Workspace'} 
        />
      )}

      <div className="mt-8 text-center text-sm text-text-muted font-sans">
        Already have a workspace?{' '}
        <Link href="/login" className="font-bold text-primary hover:underline">
          Sign in
        </Link>
      </div>
    </div>
  );
};
