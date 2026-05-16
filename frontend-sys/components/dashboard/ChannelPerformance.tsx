import { Camera, MessageCircle, Share2, Video, TrendingUp, TrendingDown } from 'lucide-react';

const channels = [
  {
    name: 'Instagram',
    icon: Camera,
    orders: '1,240',
    revenue: '320k',
    trend: '+14%',
    isUp: true,
    color: 'text-pink-600',
    bgColor: 'bg-pink-50'
  },
  {
    name: 'WhatsApp',
    icon: MessageCircle,
    orders: '980',
    revenue: '240k',
    trend: '+8%',
    isUp: true,
    color: 'text-green-600',
    bgColor: 'bg-green-50'
  },
  {
    name: 'Facebook',
    icon: Share2,
    orders: '850',
    revenue: '180k',
    trend: '-2%',
    isUp: false,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50'
  },
  {
    name: 'TikTok',
    icon: Video,
    orders: '422',
    revenue: '80k',
    trend: '+24%',
    isUp: true,
    color: 'text-black dark:text-white',
    bgColor: 'bg-zinc-100 dark:bg-zinc-800'
  }
];

export const ChannelPerformance = () => {
  return (
    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-4 shadow-sm h-full">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-bold text-zinc-900 dark:text-white">Channel Performance</h3>
          <p className="text-[10px] text-zinc-500 uppercase tracking-tight">Revenue & orders</p>
        </div>
        <button className="text-[11px] font-bold text-primary hover:underline">
          View All
        </button>
      </div>

      <div className="space-y-2">
        {channels.map((channel) => (
          <div key={channel.name} className="flex items-center justify-between p-2.5 rounded-xl hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors border border-transparent hover:border-zinc-100 dark:hover:border-zinc-800">
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${channel.bgColor} ${channel.color}`}>
                <channel.icon size={16} />
              </div>
              <div>
                <p className="text-sm font-bold text-zinc-900 dark:text-zinc-100">{channel.name}</p>
                <p className="text-[10px] text-zinc-400 font-medium">{channel.orders} orders</p>
              </div>
            </div>
            
            <div className="text-right">
              <p className="text-sm font-bold text-zinc-900 dark:text-zinc-100">{channel.revenue}</p>
              <div className={`flex items-center justify-end gap-0.5 text-[10px] font-bold ${channel.isUp ? 'text-green-600' : 'text-red-600'}`}>
                {channel.isUp ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                {channel.trend}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
