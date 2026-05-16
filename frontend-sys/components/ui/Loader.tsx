'use client';

import { cn } from '@/lib/utils';

interface LoaderProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  variant?: 'primary' | 'white' | 'zinc';
  fullScreen?: boolean;
  text?: string;
  className?: string;
}

export const Loader = ({
  size = 'md',
  variant = 'primary',
  fullScreen = false,
  text,
  className
}: LoaderProps) => {
  const sizeClasses = {
    sm: 'w-4 h-4 border-2',
    md: 'w-8 h-8 border-3',
    lg: 'w-12 h-12 border-4',
    xl: 'w-16 h-16 border-[5px]',
  };

  const variantClasses = {
    primary: 'border-primary/20 border-t-primary',
    white: 'border-white/20 border-t-white',
    zinc: 'border-zinc-200 dark:border-zinc-800 border-t-zinc-900 dark:border-t-zinc-100',
  };

  const loaderContent = (
    <div className={cn("flex flex-col items-center justify-center gap-3", className)}>
      <div 
        className={cn(
          "rounded-full animate-spin transition-all duration-300",
          sizeClasses[size],
          variantClasses[variant]
        )} 
      />
      {text && (
        <p className={cn(
          "text-xs font-bold animate-pulse tracking-wider uppercase",
          variant === 'white' ? 'text-white' : 'text-zinc-500'
        )}>
          {text}
        </p>
      )}
    </div>
  );

  if (fullScreen) {
    return (
      <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-white/80 dark:bg-black/80 backdrop-blur-sm">
        {loaderContent}
      </div>
    );
  }

  return loaderContent;
};
