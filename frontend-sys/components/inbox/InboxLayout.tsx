import React from 'react';
import { InboxSidebar } from './InboxSidebar';
import { ChatWindow } from './ChatWindow';
import { ContextPanel } from './ContextPanel';

const InboxLayout = () => {
  return (
    <div className="flex h-[calc(100vh-64px)] w-full overflow-hidden bg-[#EBF1FB]">
      {/* Zone B: Sidebar */}
      <InboxSidebar />
      
      {/* Zone C: Main Chat Area */}
      <ChatWindow />
      
      {/* Zone D: Context Panel */}
      <ContextPanel />
    </div>
  );
};

export default InboxLayout;
