'use client';

import { useForm, SubmitHandler } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { ArrowRight, Building2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { 
  Field, 
  FieldLabel, 
  FieldError, 
  FieldGroup,
  FieldContent 
} from '@/components/ui/field';

const orgSchema = z.object({
  organizationName: z.string().min(2, 'Organization name must be at least 2 characters'),
});

type OrgData = z.infer<typeof orgSchema>;

interface SignupFormOrgDetailProps {
  onNext: (data: OrgData) => void;
  defaultValues?: Partial<OrgData>;
}

export const SignupFormOrgDetail = ({ onNext, defaultValues }: SignupFormOrgDetailProps) => {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<OrgData>({
    resolver: zodResolver(orgSchema),
    defaultValues: {
      organizationName: defaultValues?.organizationName || '',
    },
  });

  const onSubmit: SubmitHandler<OrgData> = (data) => {
    onNext(data);
  };

  return (
    <div className="auth-card w-full animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex flex-col space-y-8">
        <div className="flex flex-col space-y-2 text-center">
          <h1 className="text-3xl font-bold tracking-tight text-text-primary font-heading">
            Name your workspace
          </h1>
          <p className="text-sm text-muted-foreground font-sans">
            This is where your team will manage all conversations.
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="organizationName">Organization Name</FieldLabel>
              <FieldContent className="relative">
                <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-muted-foreground z-10">
                  <Building2 className="h-4 w-4" />
                </div>
                <Input
                  {...register('organizationName')}
                  id="organizationName"
                  placeholder="e.g. Acme Corp"
                  className="pl-10 bg-white/70 rounded-xl h-12 text-lg font-medium"
                />
              </FieldContent>
              <FieldError errors={[errors.organizationName]} />
            </Field>
          </FieldGroup>

          <div className="pt-2">
            <Button
              type="submit"
              className="brand-gradient group relative flex h-12 w-full items-center justify-center overflow-hidden rounded-xl text-white transition-all hover:opacity-90 active:scale-[0.98]"
            >
              <span className="relative z-10 flex items-center gap-2 font-bold font-sans">
                <span>Continue to Profile</span>
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </span>
            </Button>
          </div>
        </form>

        <div className="flex flex-col items-center space-y-4 pt-2">
          <p className="text-xs text-center text-text-muted font-sans max-w-[280px]">
            Connect seamlessly with your favorite social platforms and start growing your business.
          </p>
          <div className="flex items-center gap-4 opacity-50 grayscale hover:grayscale-0 transition-all duration-300">
            {/* Platform Icons Silhouettes */}
            <div className="w-5 h-5 bg-text-muted rounded-sm" />
            <div className="w-5 h-5 bg-text-muted rounded-full" />
            <div className="w-5 h-5 bg-text-muted rounded-md" />
            <div className="w-5 h-5 bg-text-muted rounded-full" />
          </div>
        </div>
      </div>
    </div>
  );
};
