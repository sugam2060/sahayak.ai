import { AuthBackgroundProps } from '@/types/auth';
import { cn } from '@/lib/utils';

export const AuthBackground = ({ 
  showMesh = true, 
  animate = true, 
  className 
}: AuthBackgroundProps) => {
  return (
    <div className={cn("fixed inset-0 -z-10 overflow-hidden bg-bg-canvas", className)}>
      <div className="absolute top-0 left-0 h-[500px] w-[500px] rounded-full bg-[#CCBDFF] opacity-20 blur-[100px]" />
      <div className="absolute bottom-0 right-0 h-[500px] w-[500px] rounded-full bg-[#A3C9FF] opacity-20 blur-[100px]" />
      
      {showMesh && (
        <svg className="absolute inset-0 h-full w-full opacity-[0.15]" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="grid" width="100" height="100" patternUnits="userSpaceOnUse">
              <circle cx="2" cy="2" r="1.5" fill="#7C63D4" />
              <path d="M 100 0 L 0 0 0 100" fill="none" stroke="#5E9EEB" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
          
          <g className={cn(animate && "animate-pulse")}>
            <circle cx="10%" cy="20%" r="4" fill="#7C63D4" opacity="0.4" />
            <circle cx="85%" cy="15%" r="6" fill="#5E9EEB" opacity="0.3" />
            <circle cx="40%" cy="85%" r="5" fill="#7C63D4" opacity="0.4" />
            <circle cx="70%" cy="60%" r="3" fill="#5E9EEB" opacity="0.5" />
          </g>
          
          <line x1="10%" y1="20%" x2="40%" y2="85%" stroke="#7C63D4" strokeWidth="1" strokeDasharray="5,5" opacity="0.2" />
          <line x1="85%" y1="15%" x2="70%" y2="60%" stroke="#5E9EEB" strokeWidth="1" strokeDasharray="5,5" opacity="0.2" />
        </svg>
      )}
      
      <div className="absolute top-[15%] left-[5%] h-32 w-24 -rotate-12 rounded-2xl bg-white/10 shadow-lg backdrop-blur-sm" />
      <div className="absolute top-[60%] right-[8%] h-28 w-28 rotate-6 rounded-2xl bg-white/10 shadow-lg backdrop-blur-sm" />
      <div className="absolute bottom-[10%] left-[15%] h-24 w-32 -rotate-6 rounded-2xl bg-white/10 shadow-lg backdrop-blur-sm" />
    </div>
  );
};
