import React from 'react';
import { Search, Filter, MessageCircle } from 'lucide-react';
import { FaInstagram, FaTwitter } from 'react-icons/fa';

const conversations = [
  {
    id: 1,
    name: 'Sarah Martinez',
    lastMessage: 'Yes, the order #492 arrived but the size is slightly different than expected.',
    time: '10:42 AM',
    platform: 'instagram',
    unread: 3,
    status: 'open',
    tags: ['VIP', 'Repeat Buyer']
  },
  {
    id: 2,
    name: 'Alex Chen',
    lastMessage: 'Thanks for the tracking update!',
    time: 'Yesterday',
    platform: 'whatsapp',
    unread: 0,
    status: 'pending'
  },
  {
    id: 3,
    name: 'Marcus Johnson',
    lastMessage: 'Are these available in XL?',
    time: '2 days ago',
    platform: 'twitter',
    unread: 0,
    status: 'bot'
  }
];

export const InboxSidebar = () => {
  return (
    <div className="w-[300px] h-full flex flex-col border-r border-indigo-100/50 bg-white/70 backdrop-blur-xl">
      <div className="p-4 space-y-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input 
            type="text" 
            placeholder="Search conversations..." 
            className="w-full pl-10 pr-4 py-2 bg-slate-100/50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
          />
        </div>
        
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar pb-2">
          {['All', 'Unread', 'Mine', 'Bot'].map((filter) => (
            <button 
              key={filter}
              className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors
                ${filter === 'All' ? 'bg-indigo-50 text-indigo-600 border border-indigo-200' : 'bg-white/50 text-slate-600 border border-slate-200 hover:bg-slate-50'}`}
            >
              {filter}
            </button>
          ))}
          <button className="p-1.5 rounded-full bg-white/50 border border-slate-200 text-slate-500">
            <Filter className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="px-4 py-2">
          <span className="text-[10px] font-bold text-slate-400 tracking-wider uppercase">Today</span>
        </div>
        {conversations.map((convo) => (
          <div 
            key={convo.id}
            className={`px-4 py-3 flex gap-3 cursor-pointer transition-all border-l-4 
              ${convo.id === 1 ? 'bg-indigo-50/50 border-indigo-600' : 'border-transparent hover:bg-slate-50/50'}`}
          >
            <div className="relative flex-shrink-0">
              <div className="w-12 h-12 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-bold border-2 border-white shadow-sm">
                {convo.name.split(' ').map(n => n[0]).join('')}
              </div>
              <div className="absolute -right-0.5 -bottom-0.5 w-5 h-5 rounded-full bg-white p-1 shadow-sm border border-slate-100">
                {convo.platform === 'instagram' && <FaInstagram className="w-full h-full text-pink-600" />}
                {convo.platform === 'whatsapp' && <MessageCircle className="w-full h-full text-green-500" />}
                {convo.platform === 'twitter' && <FaTwitter className="w-full h-full text-blue-400" />}
              </div>
              <div className={`absolute -left-0.5 -top-0.5 w-3 h-3 rounded-full border-2 border-white
                ${convo.status === 'open' ? 'bg-teal-500' : convo.status === 'pending' ? 'bg-amber-500' : 'bg-indigo-500'}`} 
              />
            </div>
            
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1">
                <h4 className="text-sm font-semibold text-slate-900 truncate">{convo.name}</h4>
                <span className="text-[10px] font-medium text-slate-400">{convo.time}</span>
              </div>
              <p className="text-xs text-slate-500 line-clamp-1 mb-2">
                {convo.lastMessage}
              </p>
              <div className="flex items-center justify-between">
                <div className="flex gap-1.5">
                  {convo.tags?.map(tag => (
                    <span key={tag} className="px-1.5 py-0.5 bg-indigo-50 text-[9px] font-bold text-indigo-600 rounded-sm uppercase tracking-tight">
                      {tag}
                    </span>
                  ))}
                  {convo.status === 'bot' && (
                    <span className="flex items-center gap-1 text-[10px] font-medium text-indigo-500">
                      <div className="w-1 h-1 rounded-full bg-indigo-500" />
                      Bot handling
                    </span>
                  )}
                </div>
                {convo.unread > 0 && (
                  <div className="px-1.5 py-0.5 rounded-full bg-gradient-to-br from-indigo-500 to-blue-500 text-[10px] font-bold text-white min-w-[18px] flex items-center justify-center">
                    {convo.unread}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
