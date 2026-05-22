'use client';

import Link from 'next/link';
import { useForm, SubmitHandler } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Mail, Lock, ArrowRight, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { 
  Field, 
  FieldLabel, 
  FieldError, 
  FieldGroup,
  FieldContent 
} from '@/components/ui/field';
import { LoginData } from '@/types/auth';

import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useRouter } from 'next/navigation';
import { loginUser } from '@/services/api/auth';

import { useAuthStore } from '@/store/authStore';

const loginSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(6, 'Password must be at least 6 characters'),
});

export const LoginForm = () => {
  const router = useRouter();
  const setAuth = useAuthStore((state) => state.setAuth);
  const form = useForm<LoginData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = form;

  const mutation = useMutation({
    mutationFn: loginUser,
    onSuccess: (data) => {
      if (data.success && data.user_id) {
        toast.success(data.message);
        setAuth(data);
        router.push('/');
      } else if (data.is_verified === false) {
        toast.warning(data.message);
      }
    },
    onError: (error: Error) => {
      toast.error(error.message);
    }
  });

  const onSubmit: SubmitHandler<LoginData> = async (data) => {
    try {
      await mutation.mutateAsync(data);
    } catch {
      // Error is handled by mutation.onError
    }
  };

  return (
    <div className="auth-card w-full animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex flex-col space-y-8">
        <div className="flex flex-col space-y-2 text-center">
          <h1 className="text-3xl font-bold tracking-tight text-text-primary font-heading">
            Welcome back
          </h1>
          <p className="text-sm text-muted-foreground font-sans">
            Enter your credentials to access your workspace
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="email">Work Email</FieldLabel>
              <FieldContent className="relative">
                <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-muted-foreground z-10">
                  <Mail className="h-4 w-4" />
                </div>
                <Input
                  {...register('email')}
                  id="email"
                  type="email"
                  placeholder="name@company.com"
                  className="pl-10 bg-white/70 rounded-xl h-11"
                />
              </FieldContent>
              <FieldError errors={[errors.email]} />
            </Field>

            <Field>
              <div className="flex items-center justify-between">
                <FieldLabel htmlFor="password">Password</FieldLabel>
                <Link
                  href="/forgot-password"
                  className="text-xs font-medium text-primary hover:underline font-sans"
                >
                  Forgot password?
                </Link>
              </div>
              <FieldContent className="relative">
                <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-muted-foreground z-10">
                  <Lock className="h-4 w-4" />
                </div>
                <Input
                  {...register('password')}
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  className="pl-10 bg-white/70 rounded-xl h-11"
                />
              </FieldContent>
              <FieldError errors={[errors.password]} />
            </Field>
          </FieldGroup>

          <Button
            disabled={isSubmitting}
            type="submit"
            className="brand-gradient group relative flex h-12 w-full items-center justify-center overflow-hidden rounded-xl text-white transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-70"
          >
            <span className="relative z-10 flex items-center gap-2 font-bold font-sans">
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Signing in...</span>
                </>
              ) : (
                <>
                  <span>Sign in to workspace</span>
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                </>
              )}
            </span>
          </Button>
        </form>

        <div className="text-center text-sm text-text-muted font-sans">
          Don&apos;t have a workspace?{' '}
          <Link href="/signup" className="font-bold text-primary hover:underline">
            Create one for free
          </Link>
        </div>
      </div>
    </div>
  );
};
