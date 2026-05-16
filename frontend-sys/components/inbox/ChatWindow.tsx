import React from 'react';
import { MoreHorizontal, Paperclip, ImageIcon, Package, ShoppingBag, Sparkles, Send, CheckCircle2 } from 'lucide-react';

export const ChatWindow = () => {
  return (
    <div className="flex-1 flex flex-col bg-white/50 backdrop-blur-sm relative overflow-hidden">
      {/* Header */}
      <div className="h-16 flex items-center justify-between px-6 border-b border-indigo-100/50 bg-white/80 backdrop-blur-md z-10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-bold border border-white">
            SM
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-slate-900">Sarah Martinez</h3>
              <span className="px-2 py-0.5 rounded-full bg-indigo-50 text-[10px] font-bold text-indigo-600 uppercase">Instagram DM</span>
            </div>
            <p className="text-[10px] text-slate-400 font-medium">@sarah.m • Last seen 2m ago</p>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="flex items-center bg-slate-100/50 border border-slate-200 rounded-lg p-1">
             <button className="px-3 py-1.5 text-[10px] font-bold text-slate-600 hover:bg-white rounded-md transition-all uppercase tracking-wider">Assign</button>
             <div className="w-px h-3 bg-slate-300 mx-1" />
             <button className="px-3 py-1.5 text-[10px] font-bold text-teal-600 hover:bg-white rounded-md transition-all uppercase tracking-wider">Resolve</button>
          </div>
          <button className="p-2 text-slate-400 hover:text-slate-600 transition-colors">
            <MoreHorizontal className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-8">
        <div className="flex justify-center">
          <div className="px-4 py-1.5 rounded-full bg-slate-100 text-[10px] font-bold text-slate-400 uppercase tracking-widest font-mono">
            Mon, 14 Apr 2025
          </div>
        </div>

        {/* Inbound Message */}
        <div className="flex gap-3 max-w-[70%] group">
          <div className="w-8 h-8 rounded-full bg-indigo-100 flex-shrink-0 flex items-center justify-center text-[10px] font-bold text-indigo-600">SM</div>
          <div className="space-y-1">
            <div className="p-4 bg-white/80 backdrop-blur-md border border-indigo-50 rounded-2xl rounded-tl-none shadow-sm text-sm text-slate-700 leading-relaxed">
              Yes, the order #492 arrived but the size is slightly different than expected. Is there a way I can exchange it for a Medium instead of a Large?
            </div>
            <span className="text-[10px] font-medium text-slate-400 pl-1">10:42 AM • Instagram</span>
          </div>
        </div>

        {/* Outbound Message */}
        <div className="flex flex-row-reverse gap-3 max-w-[70%] ml-auto">
          <div className="w-8 h-8 rounded-full bg-indigo-600 flex-shrink-0 flex items-center justify-center text-[10px] font-bold text-white shadow-lg">YO</div>
          <div className="space-y-1 items-end flex flex-col">
            <div className="p-4 bg-indigo-50 border border-indigo-200 rounded-2xl rounded-tr-none text-sm text-slate-800 leading-relaxed shadow-sm">
              Hi Sarah! I&apos;m sorry to hear about the sizing issue. Of course, we can process an exchange for you. I&apos;ve checked our stock and we do have the Navy Blue Linen Shirt in Medium available.
            </div>
            <div className="flex items-center gap-2 pr-1">
               <span className="text-[10px] font-medium text-slate-400">10:45 AM</span>
               <CheckCircle2 className="w-3 h-3 text-indigo-500" />
            </div>
          </div>
        </div>

        {/* Order Card Embedded */}
        <div className="max-w-[80%] mx-auto py-4">
          <div className="bg-white border-2 border-indigo-50 rounded-2xl shadow-xl overflow-hidden group hover:border-indigo-200 transition-all">
            <div className="bg-indigo-50/50 px-6 py-3 flex items-center justify-between border-b border-indigo-100">
               <div className="flex items-center gap-2">
                 <Package className="w-4 h-4 text-indigo-600" />
                 <span className="text-xs font-bold text-slate-800 tracking-tight uppercase">Order #492</span>
               </div>
               <span className="px-2 py-0.5 rounded-full bg-teal-100 text-[9px] font-black text-teal-700 uppercase tracking-widest">Delivered</span>
            </div>
            <div className="p-6">
               <div className="flex gap-4 mb-4">
                 <div className="w-16 h-16 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center text-[10px] font-bold text-slate-400">IMG</div>
                 <div className="flex-1">
                    <h4 className="text-sm font-bold text-slate-900">Navy Blue Linen Shirt</h4>
                    <p className="text-xs text-slate-500 font-medium">Size: Large • Qty: 1</p>
                    <div className="mt-1 flex items-center gap-2">
                       <span className="text-xs font-black text-indigo-600">$85.00</span>
                    </div>
                 </div>
               </div>
               <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-100">
                  <button className="px-4 py-2 text-xs font-bold text-indigo-600 bg-indigo-50 rounded-lg hover:bg-indigo-100 transition-all uppercase tracking-wide">View Order</button>
                  <button className="px-4 py-2 text-xs font-bold text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-all uppercase tracking-wide">Track Shipment</button>
               </div>
            </div>
          </div>
        </div>
      </div>

      {/* Reply Bar */}
      <div className="px-6 py-6 border-t border-indigo-100/50 bg-white/80 backdrop-blur-xl space-y-4">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-4">
            <button className="text-slate-400 hover:text-indigo-600 transition-colors p-1"><Paperclip className="w-5 h-5" /></button>
            <button className="text-slate-400 hover:text-indigo-600 transition-colors p-1"><ImageIcon className="w-5 h-5" /></button>
            <button className="text-slate-400 hover:text-indigo-600 transition-colors p-1"><Package className="w-5 h-5" /></button>
            <button className="text-slate-400 hover:text-indigo-600 transition-colors p-1"><ShoppingBag className="w-5 h-5" /></button>
          </div>
        </div>

        <div className="flex gap-3">
          <div className="flex-1 relative">
            <textarea 
              placeholder="Reply to Sarah Martinez..."
              className="w-full bg-slate-100/50 border-2 border-indigo-50 rounded-2xl px-6 py-4 text-sm focus:outline-none focus:border-indigo-600/30 transition-all resize-none min-h-[56px] max-h-40 placeholder:text-slate-400"
            />
            <button className="absolute right-3 top-3.5 p-1.5 rounded-lg bg-gradient-to-br from-indigo-500 to-blue-500 text-white shadow-lg shadow-indigo-200 hover:scale-105 active:scale-95 transition-all">
              <Sparkles className="w-4 h-4" />
            </button>
          </div>
          <button className="h-[56px] w-[56px] rounded-2xl bg-indigo-600 flex items-center justify-center text-white shadow-xl shadow-indigo-100 hover:bg-indigo-700 active:scale-95 transition-all">
            <Send className="w-5 h-5" />
          </button>
        </div>

        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest font-mono">Via: Instagram DM</span>
            <button className="text-[10px] font-bold text-indigo-500 hover:underline uppercase tracking-widest">Switch Channel</button>
          </div>
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest font-mono">Press ⌘ + Enter to send</span>
        </div>
      </div>
    </div>
  );
};
