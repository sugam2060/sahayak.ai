'use client';

import { useForm, SubmitHandler } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Mail, Lock, User, ArrowLeft, ArrowRight, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { 
  Field, 
  FieldLabel, 
  FieldError, 
  FieldGroup,
  FieldContent 
} from '@/components/ui/field';

const userSchema = z.object({
  fullName: z.string().min(2, 'Full name must be at least 2 characters'),
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  confirmPassword: z.string().min(8, 'Please confirm your password'),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
});

type UserData = z.infer<typeof userSchema>;

interface SignupFormUserDetailProps {
  onBack: () => void;
  onSubmit: (data: UserData) => void;
  orgName: string;
}

export const SignupFormUserDetail = ({ onBack, onSubmit, orgName }: SignupFormUserDetailProps) => {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<UserData>({
    resolver: zodResolver(userSchema),
  });

  const handleSignup: SubmitHandler<UserData> = async (data) => {
    await onSubmit(data);
  };

  return (
    <div className="auth-card w-full animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex flex-col space-y-8">
        <div className="flex flex-col space-y-2 text-center">
          <div className="mx-auto inline-flex px-3 py-1 bg-primary/10 text-primary rounded-full text-xs font-bold mb-2">
            {orgName}
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-text-primary font-heading">
            Create your profile
          </h1>
          <p className="text-sm text-muted-foreground font-sans">
            Set up your personal operator account.
          </p>
        </div>

        <form onSubmit={handleSubmit(handleSignup)} className="space-y-4">
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="fullName">Full Name</FieldLabel>
              <FieldContent className="relative">
                <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-muted-foreground z-10">
                  <User className="h-4 w-4" />
                </div>
                <Input
                  {...register('fullName')}
                  id="fullName"
                  placeholder="John Doe"
                  className="pl-10 bg-white/70 rounded-xl h-11"
                />
              </FieldContent>
              <FieldError errors={[errors.fullName]} />
            </Field>

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
              <FieldLabel htmlFor="password">Password</FieldLabel>
              <FieldContent className="relative">
                <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-muted-foreground z-10">
                  <Lock className="h-4 w-4" />
                </div>
                <Input
                  {...register('password')}
                  id="password"
                  type="password"
                  placeholder="Minimum 8 characters"
                  className="pl-10 bg-white/70 rounded-xl h-11"
                />
              </FieldContent>
              <FieldError errors={[errors.password]} />
            </Field>

            <Field>
              <FieldLabel htmlFor="confirmPassword">Confirm Password</FieldLabel>
              <FieldContent className="relative">
                <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-muted-foreground z-10">
                  <Lock className="h-4 w-4" />
                </div>
                <Input
                  {...register('confirmPassword')}
                  id="confirmPassword"
                  type="password"
                  placeholder="Repeat your password"
                  className="pl-10 bg-white/70 rounded-xl h-11"
                />
              </FieldContent>
              <FieldError errors={[errors.confirmPassword]} />
            </Field>
          </FieldGroup>

          <div className="flex gap-4 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={onBack}
              className="h-12 w-24 rounded-xl border-border bg-white/50 text-text-primary hover:bg-white/80"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back
            </Button>
            <Button
              disabled={isSubmitting}
              type="submit"
              className="brand-gradient group relative flex h-12 flex-1 items-center justify-center overflow-hidden rounded-xl text-white transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-70"
            >
              <span className="relative z-10 flex items-center gap-2 font-bold font-sans">
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Creating workspace...</span>
                  </>
                ) : (
                  <>
                    <span>Create workspace</span>
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                  </>
                )}
              </span>
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
