import React from 'react';
import { Mail, Phone, DollarSign, History, ChevronRight, ExternalLink } from 'lucide-react';

export const ContextPanel = () => {
  return (
    <div className="w-[320px] h-full flex flex-col bg-white/70 backdrop-blur-2xl border-l border-indigo-100/50">
      {/* Tabs */}
      <div className="flex border-b border-indigo-50">
        {['Customer', 'Orders', 'Notes'].map((tab, i) => (
          <button 
            key={tab}
            className={`flex-1 py-4 text-[10px] font-black uppercase tracking-widest transition-all
              ${i === 0 ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-slate-400 hover:text-slate-600'}`}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto no-scrollbar">
        {/* Profile Section */}
        <div className="p-6 text-center space-y-4">
          <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-indigo-100 to-blue-50 mx-auto flex items-center justify-center text-2xl font-black text-indigo-600 shadow-inner border-2 border-white">
            SM
          </div>
          <div>
            <h3 className="text-base font-black text-slate-900 tracking-tight">Sarah Martinez</h3>
            <p className="text-xs text-indigo-500 font-bold uppercase tracking-widest mt-1">VIP Customer</p>
          </div>
          
          <div className="flex justify-center gap-2">
            <span className="px-2 py-1 rounded-md bg-indigo-50 text-[9px] font-bold text-indigo-600 uppercase tracking-tighter">Repeat Buyer</span>
            <span className="px-2 py-1 rounded-md bg-blue-50 text-[9px] font-bold text-blue-600 uppercase tracking-tighter">Since Mar 2024</span>
          </div>
        </div>

        {/* Contact Info */}
        <div className="px-6 space-y-3">
          <div className="p-3 rounded-xl bg-white/40 border border-indigo-50 flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-500">
              <Mail className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Email</p>
              <p className="text-xs font-medium text-slate-700 truncate">sarah.m@example.com</p>
            </div>
            <ExternalLink className="w-3 h-3 text-slate-300" />
          </div>
          <div className="p-3 rounded-xl bg-white/40 border border-indigo-50 flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-500">
              <Phone className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Phone</p>
              <p className="text-xs font-medium text-slate-700">+977 9801234567</p>
            </div>
          </div>
        </div>

        {/* Lifetime Stats */}
        <div className="p-6">
          <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-4 flex items-center gap-2">
             <DollarSign className="w-3 h-3" /> Lifetime Value
          </h4>
          <div className="grid grid-cols-2 gap-4">
             <div className="p-4 rounded-2xl bg-gradient-to-br from-white to-indigo-50/30 border border-indigo-50 shadow-sm">
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Total Spent</p>
                <p className="text-lg font-black text-indigo-600 tracking-tight">$340.00</p>
             </div>
             <div className="p-4 rounded-2xl bg-gradient-to-br from-white to-blue-50/30 border border-blue-50 shadow-sm">
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Orders</p>
                <p className="text-lg font-black text-blue-600 tracking-tight">4</p>
             </div>
          </div>
        </div>

        {/* Customer Story */}
        <div className="px-6 pb-8">
           <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-6 flex items-center gap-2">
             <History className="w-3 h-3" /> Customer Story
          </h4>
          
          <div className="relative pl-6 space-y-8 border-l border-indigo-100 ml-1.5">
             {[
               { time: 'Today, 10:42 AM', event: 'Inquired about size exchange', order: '#492' },
               { time: 'Yesterday, 2:30 PM', event: 'Order #492 marked as Delivered', color: 'text-teal-600' },
               { time: 'Oct 20, 9:00 AM', event: 'Opened "Fall Collection Drop" Email' },
               { time: 'Oct 18, 4:15 PM', event: 'Placed Order #492', value: '$85.00' }
             ].map((item, i) => (
               <div key={i} className="relative">
                 <div className="absolute -left-[27px] top-0.5 w-3 h-3 rounded-full bg-white border-2 border-indigo-500 shadow-sm" />
                 <p className="text-[9px] font-bold text-indigo-400 uppercase tracking-widest mb-1">{item.time}</p>
                 <div className="bg-white/50 p-3 rounded-xl border border-indigo-50/50 group hover:border-indigo-200 transition-all cursor-pointer">
                    <p className={`text-xs font-semibold ${item.color || 'text-slate-700'}`}>{item.event}</p>
                    {(item.order || item.value) && (
                      <div className="mt-2 flex items-center justify-between">
                         <span className="text-[10px] font-bold text-indigo-500 bg-indigo-50 px-1.5 py-0.5 rounded uppercase tracking-tighter">{item.order || item.value}</span>
                         <ChevronRight className="w-3 h-3 text-slate-300 group-hover:text-indigo-400 transition-colors" />
                      </div>
                    )}
                 </div>
               </div>
             ))}
          </div>
          
          <button className="w-full mt-6 py-3 rounded-xl border-2 border-dashed border-indigo-100 text-[10px] font-black text-indigo-400 uppercase tracking-widest hover:bg-indigo-50/30 hover:border-indigo-200 transition-all">
             Load More History
          </button>
        </div>
      </div>
    </div>
  );
};
