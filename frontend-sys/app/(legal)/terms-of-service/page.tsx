import React from 'react';

export default function TermsOfService() {
  return (
    <div className="prose prose-slate max-w-none">
      <h1 className="text-4xl font-black text-[#1E1B4B] mb-8 tracking-tight">Terms of Service</h1>
      <p className="text-slate-500 font-medium italic mb-12">Last Updated: May 16, 2026</p>

      <section className="space-y-6">
        <h2 className="text-2xl font-black text-[#1E1B4B] flex items-center gap-3">
          <div className="w-2 h-8 bg-[#7C63D4] rounded-full" />
          1. Acceptance of Terms
        </h2>
        <p className="text-slate-600 leading-relaxed">
          By connecting your TikTok account to Sahayak AI, you agree to be bound by these Terms of Service and all applicable laws and regulations. If you do not agree with any of these terms, you are prohibited from using the TikTok Integration.
        </p>
      </section>

      <section className="mt-12 space-y-6">
        <h2 className="text-2xl font-black text-[#1E1B4B] flex items-center gap-3">
          <div className="w-2 h-8 bg-[#5E9EEB] rounded-full" />
          2. The TikTok Integration
        </h2>
        <p className="text-slate-600 leading-relaxed">
          Sahayak AI provides a tool to manage TikTok interactions via our Omnichannel Inbox. We are not affiliated with TikTok, and your use of TikTok is governed by TikTok&apos;s own Terms of Service. You are responsible for ensuring your use of our platform complies with TikTok&apos;s rules and policies.
        </p>
      </section>

      <section className="mt-12 space-y-6">
        <h2 className="text-2xl font-black text-[#1E1B4B] flex items-center gap-3">
          <div className="w-2 h-8 bg-[#7C63D4] rounded-full" />
          3. User Responsibilities
        </h2>
        <ul className="list-disc pl-6 space-y-4 text-slate-600">
          <li><strong>Account Security:</strong> You are responsible for maintaining the confidentiality of your Sahayak AI and TikTok credentials.</li>
          <li><strong>Content Ownership:</strong> You retain all rights to the content you post on TikTok. By using our service, you grant us a temporary license to process this content for the sole purpose of displaying it in your inbox.</li>
          <li><strong>Lawful Use:</strong> You agree not to use the TikTok Connector for any illegal purposes or to distribute spam, harassment, or malicious content.</li>
        </ul>
      </section>

      <section className="mt-12 space-y-6">
        <h2 className="text-2xl font-black text-[#1E1B4B] flex items-center gap-3">
          <div className="w-2 h-8 bg-[#5E9EEB] rounded-full" />
          4. AI-Assisted Responses
        </h2>
        <p className="text-slate-600 leading-relaxed">
          Our service provides AI-generated response suggestions. You acknowledge that you are solely responsible for reviewing and approving any AI-suggested content before it is sent to a third party. Sahayak AI is not liable for the accuracy or appropriateness of AI suggestions.
        </p>
      </section>

      <section className="mt-12 space-y-6">
        <h2 className="text-2xl font-black text-[#1E1B4B] flex items-center gap-3">
          <div className="w-2 h-8 bg-[#7C63D4] rounded-full" />
          5. Limitation of Liability
        </h2>
        <p className="text-slate-600 leading-relaxed">
          Sahayak AI shall not be held liable for any damages resulting from the use or inability to use the TikTok Integration, including but not limited to account suspensions by TikTok or loss of data resulting from API changes.
        </p>
      </section>

      <section className="mt-12 space-y-6">
        <h2 className="text-2xl font-black text-[#1E1B4B] flex items-center gap-3">
          <div className="w-2 h-8 bg-[#5E9EEB] rounded-full" />
          6. Termination
        </h2>
        <p className="text-slate-600 leading-relaxed">
          We reserve the right to suspend or terminate your access to the TikTok Integration at any time, without notice, for conduct that we believe violates these Terms or is harmful to other users or our business interests.
        </p>
      </section>

      <section className="mt-16 pt-8 border-t border-slate-100 flex items-center justify-between">
        <p className="text-slate-400 text-sm">Need help? Contact legal@sahayak.ai</p>
        <div className="flex gap-4">
          <button className="px-6 py-2 bg-gradient-to-br from-[#7C63D4] to-[#5E9EEB] text-white text-xs font-black uppercase tracking-widest rounded-xl shadow-lg shadow-indigo-100 hover:scale-105 transition-all">
            Download PDF
          </button>
        </div>
      </section>
    </div>
  );
}
