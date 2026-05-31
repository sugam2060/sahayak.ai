import React from 'react';

export default function PrivacyPolicy() {
  return (
    <div className="prose prose-slate max-w-none">
      <h1 className="text-4xl font-black text-[#1E1B4B] mb-8 tracking-tight">Privacy Policy</h1>
      <p className="text-slate-500 font-medium italic mb-12">Last Updated: May 31, 2026</p>

      <section className="space-y-6">
        <h2 className="text-2xl font-black text-[#1E1B4B] flex items-center gap-3">
          <div className="w-2 h-8 bg-[#7C63D4] rounded-full" />
          1. Introduction
        </h2>
        <p className="text-slate-600 leading-relaxed">
          Sahayak AI (&quot;we,&quot; &quot;our,&quot; or &quot;us&quot;) is committed to protecting your privacy. This Privacy Policy explains how we collect, use, and safeguard your information when you connect and integrate your social media and messaging channels, specifically our Instagram, TikTok, and Telegram integrations (&quot;Connectors&quot;).
        </p>
      </section>

      <section className="mt-12 space-y-6">
        <h2 className="text-2xl font-black text-[#1E1B4B] flex items-center gap-3">
          <div className="w-2 h-8 bg-[#5E9EEB] rounded-full" />
          2. Information We Collect via Connectors
        </h2>
        <p className="text-slate-600 leading-relaxed">
          When you authorize the Sahayak AI Instagram, TikTok, or Telegram Connectors, we may collect the following information from your connected accounts:
        </p>
        <ul className="list-disc pl-6 space-y-2 text-slate-600">
          <li><strong>Basic Profile Information:</strong> Your display name, username, profile picture/avatar, and unique platform-specific User ID.</li>
          <li><strong>Content and Chat Interaction:</strong> Direct messages, chats, comments, media attachments, and message metadata sent to your integrated accounts for the purpose of managing them in the Sahayak AI Omnichannel Inbox.</li>
          <li><strong>Access Tokens:</strong> Temporary authorization tokens and API credentials provided by the respective platforms (Meta/Instagram, TikTok, Telegram) to facilitate secure message synchronization.</li>
        </ul>
      </section>

      <section className="mt-12 space-y-6">
        <h2 className="text-2xl font-black text-[#1E1B4B] flex items-center gap-3">
          <div className="w-2 h-8 bg-[#7C63D4] rounded-full" />
          3. How We Use Your Information
        </h2>
        <p className="text-slate-600 leading-relaxed">
          We use the information collected from connected platforms strictly for the following purposes:
        </p>
        <ul className="list-disc pl-6 space-y-2 text-slate-600">
          <li>To display and manage customer chats, messages, and comments inside your Sahayak AI Omnichannel Inbox.</li>
          <li>To generate and suggest AI-assisted response options for customer support inquiries.</li>
          <li>To synchronize customer profiles and brand conversations across your multiple social channels.</li>
        </ul>
      </section>

      <section className="mt-12 space-y-6">
        <h2 className="text-2xl font-black text-[#1E1B4B] flex items-center gap-3">
          <div className="w-2 h-8 bg-[#5E9EEB] rounded-full" />
          4. Data Sharing and Disclosure
        </h2>
        <p className="text-slate-600 leading-relaxed">
          <strong>We do not sell your personal data.</strong> Your information is only shared with third-party service providers (such as database hosting, cloud storage, or AI processing APIs) as necessary to provide the Sahayak AI service. All providers are contractually obligated to protect your data.
        </p>
      </section>

      <section className="mt-12 space-y-6">
        <h2 className="text-2xl font-black text-[#1E1B4B] flex items-center gap-3">
          <div className="w-2 h-8 bg-[#7C63D4] rounded-full" />
          5. Data Retention and Deletion
        </h2>
        <p className="text-slate-600 leading-relaxed">
          We retain your social integration data only as long as your Sahayak AI account is active and connected to the respective platforms. You can request data deletion at any time by:
        </p>
        <ul className="list-disc pl-6 space-y-2 text-slate-600">
          <li>Disconnecting the specific Connector from the Sahayak AI Settings dashboard.</li>
          <li>Removing Sahayak AI&apos;s authorization permissions within your Instagram, TikTok, or Telegram application/security settings.</li>
          <li>Contacting our support team at <span className="text-[#7C63D4] font-bold">support@paperjetlabs.com</span>.</li>
        </ul>
      </section>

      <section className="mt-12 p-8 bg-indigo-50/50 rounded-2xl border border-indigo-100">
        <h3 className="text-lg font-black text-[#1E1B4B] mb-4 uppercase tracking-widest">Contact Us</h3>
        <p className="text-slate-600 text-sm">
          If you have any questions about this Privacy Policy, please contact us at:<br />
          <span className="font-bold">Sahayak AI Privacy Team</span><br />
          Email: support@paperjetlabs.com
        </p>
      </section>
    </div>
  );
}
