'use client';

import React from 'react';
import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SignupProgressProps {
  currentStep: number;
  steps: string[];
}

export const SignupProgress = ({ currentStep, steps }: SignupProgressProps) => {
  return (
    <div className="w-full max-w-md mx-auto mb-8 px-4">
      <div className="relative flex items-center justify-between">
        {/* Connection Line */}
        <div className="absolute top-1/2 left-0 w-full h-[2px] bg-blue-100 -translate-y-1/2 z-0" />
        <div 
          className="absolute top-1/2 left-0 h-[2px] bg-primary -translate-y-1/2 z-0 transition-all duration-500" 
          style={{ width: `${(currentStep / (steps.length - 1)) * 100}%` }}
        />

        {steps.map((step, index) => {
          const isCompleted = currentStep > index;
          const isActive = currentStep === index;

          return (
            <div key={step} className="relative z-10 flex flex-col items-center">
              <div
                className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center transition-all duration-300 border-2",
                  isCompleted ? "bg-primary border-primary text-white" : 
                  isActive ? "bg-white border-primary text-primary" : 
                  "bg-white border-blue-100 text-blue-100"
                )}
              >
                {isCompleted ? (
                  <Check className="h-4 w-4" />
                ) : (
                  <span className="text-xs font-bold">{index + 1}</span>
                )}
              </div>
              <span 
                className={cn(
                  "absolute top-10 whitespace-nowrap text-[10px] font-bold uppercase tracking-wider transition-all duration-300",
                  isActive || isCompleted ? "text-primary" : "text-text-muted"
                )}
              >
                {step}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
