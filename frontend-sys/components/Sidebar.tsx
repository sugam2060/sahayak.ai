'use client';

import { 
  LayoutDashboard, 
  MessageSquare, 
  Package,  
  HelpCircle,
} from 'lucide-react';
import { 
  RiPlugLine, 
  RiRobot2Line, 
  RiTeamLine,
  RiUser3Line,
  RiBox3Line,
  RiSettings4Line,
  RiBarChartGroupedLine
} from 'react-icons/ri';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export const Sidebar = () => {
  const pathname = usePathname();

  const menuItems = [
    { name: 'Dashboard', icon: LayoutDashboard, href: '/' },
    { name: 'Inbox', icon: MessageSquare, href: '/inbox' },
    { name: 'Orders', icon: Package, href: '/orders' },
    { name: 'Products', icon: RiBox3Line, href: '/products' },
    { name: 'Connectors', icon: RiPlugLine, href: '/connectors' },
    { name: 'AI Configuration', icon: RiRobot2Line, href: '/ai-config' },
    { name: 'Team Management', icon: RiTeamLine, href: '/team' },
    { name: 'User Profile', icon: RiUser3Line, href: '/profile' },
    { name: 'Analytics', icon: RiBarChartGroupedLine, href: '/analytics' },
  ];

  const bottomItems = [
    { name: 'Help', icon: HelpCircle, href: '/help' },
    { name: 'Settings', icon: RiSettings4Line, href: '/settings' },
  ];

  return (
    <aside className="w-16 bg-white dark:bg-zinc-900 border-r border-zinc-200 dark:border-zinc-800 flex flex-col h-[calc(100vh-64px)] sticky top-16 z-30 transition-all duration-300">
      <TooltipProvider delayDuration={0}>
        <div className="flex-1 flex flex-col items-center py-4 gap-2 overflow-y-auto no-scrollbar">
          {menuItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Tooltip key={item.name}>
                <TooltipTrigger asChild>
                  <Link
                    href={item.href}
                    className={`relative w-10 h-10 flex items-center justify-center rounded-xl transition-all group ${
                      isActive 
                        ? 'bg-primary text-white shadow-md shadow-primary/20' 
                        : 'text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-zinc-100'
                    }`}
                  >
                    <item.icon size={18} className="transition-transform group-hover:scale-110" />
                    {isActive && (
                      <div className="absolute -left-3 w-1 h-5 bg-primary rounded-r-full" />
                    )}
                  </Link>
                </TooltipTrigger>
                <TooltipContent side="right" sideOffset={10} className="font-semibold text-xs">
                  {item.name}
                </TooltipContent>
              </Tooltip>
            );
          })}
        </div>

        <div className="p-3 border-t border-zinc-100 dark:border-zinc-800 flex flex-col items-center gap-2">
          {bottomItems.map((item) => (
            <Tooltip key={item.name}>
              <TooltipTrigger asChild>
                <Link
                  href={item.href}
                  className="w-10 h-10 flex items-center justify-center rounded-xl text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-zinc-100 transition-all group"
                >
                  <item.icon size={18} className="group-hover:rotate-12 transition-transform" />
                </Link>
              </TooltipTrigger>
              <TooltipContent side="right" sideOffset={10} className="font-semibold text-xs">
                {item.name}
              </TooltipContent>
            </Tooltip>
          ))}
        </div>
      </TooltipProvider>
    </aside>
  );
};
