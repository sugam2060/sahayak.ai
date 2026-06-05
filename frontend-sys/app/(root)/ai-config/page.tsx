'use client';

import React, { useState, useEffect } from 'react';
import { useAIConfig, useUpdateAIConfig } from '@/services/api/ai-config';
import { toast } from 'sonner';
import {
  RiRobot2Line,
  RiFileWarningLine,
  RiUploadCloud2Line,
  RiFileTextLine,
  RiDeleteBinLine,
  RiCheckDoubleLine
} from 'react-icons/ri';
import { Loader } from '@/components/ui/Loader';

export default function AIConfigPage() {
  const { data, isLoading, error } = useAIConfig();
  const updateMutation = useUpdateAIConfig();

  const [aiEnabled, setAiEnabled] = useState(true);
  const [autoOrderEnabled, setAutoOrderEnabled] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState('');
  const [knowledgeBase, setKnowledgeBase] = useState('');
  const [isParsing, setIsParsing] = useState(false);
  const [parsedFiles, setParsedFiles] = useState<{ name: string; size: string; textLength: number }[]>([]);

  // Sync state when data is loaded
  useEffect(() => {
    if (data?.config) {
      /* eslint-disable react-hooks/set-state-in-effect */
      setAiEnabled(data.config.ai_enabled);
      setAutoOrderEnabled(data.config.auto_order_enabled);
      setSystemPrompt(data.config.system_prompt || '');
      setKnowledgeBase(data.config.knowledge_base || '');
      /* eslint-enable react-hooks/set-state-in-effect */
    }
  }, [data]);

  const handleSave = async () => {
    try {
      await updateMutation.mutateAsync({
        ai_enabled: aiEnabled,
        auto_order_enabled: autoOrderEnabled,
        system_prompt: systemPrompt,
        knowledge_base: knowledgeBase,
      });
      toast.success('AI Configuration updated successfully and synced with ChatAI Service!');
      setParsedFiles([]);
    } catch (err) {
      const error = err as Error;
      toast.error(error.message || 'Failed to update AI Configuration.');
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setIsParsing(true);
    let newText = '';

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      try {
        let text = '';
        if (file.type === 'application/pdf' || file.name.endsWith('.pdf')) {
          text = await parsePdf(file);
        } else if (
          file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
          file.name.endsWith('.docx')
        ) {
          text = await parseDocx(file);
        } else {
          toast.warning(`Unsupported file format: ${file.name}. Only PDF and DOCX are allowed.`);
          continue;
        }

        if (text.trim()) {
          newText += `\n--- Document: ${file.name} ---\n` + text.trim() + '\n';
          setParsedFiles(prev => [
            ...prev,
            {
              name: file.name,
              size: (file.size / 1024).toFixed(1) + ' KB',
              textLength: text.trim().length,
            }
          ]);
          toast.success(`Successfully parsed ${file.name}`);
        } else {
          toast.warning(`No readable text found in ${file.name}`);
        }
      } catch (err) {
        const error = err as Error;
        console.error('File parsing error:', error);
        toast.error(`Error parsing ${file.name}: ${error.message || String(error)}`);
      }
    }

    if (newText) {
      setKnowledgeBase(prev => (prev ? prev + '\n' + newText : newText.trim()));
    }
    setIsParsing(false);
    // Reset file input value
    e.target.value = '';
  };

  const parsePdf = async (file: File): Promise<string> => {
    try {
      // Dynamically import pdfjs
      const pdfjs = await import('pdfjs-dist');

      /**
       * IMPORTANT:
       * Use local bundled worker.
       * CDN worker causes issues in Next.js.
       */
      pdfjs.GlobalWorkerOptions.workerSrc = new URL(
        'pdfjs-dist/build/pdf.worker.min.mjs',
        import.meta.url
      ).toString();

      // Read file
      const arrayBuffer = await file.arrayBuffer();

      // Load PDF
      const loadingTask = pdfjs.getDocument({
        data: arrayBuffer,
      });

      const pdf = await loadingTask.promise;

      let text = '';

      // Extract text page by page
      for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);

        const content = await page.getTextContent();

        const pageText = content.items
          .map((item: unknown) => {
            // Some items may not contain `str`
            if (item && typeof item === 'object' && 'str' in item) {
              return (item as { str: string }).str;
            }

            return '';
          })
          .join(' ');

        text += pageText + '\n';
      }

      return text;
    } catch (err) {
      console.error(
        'PDF JS direct extraction failed:',
        err
      );

      throw new Error(
        'Failed to parse PDF file. Ensure it is not password-protected.'
      );
    }
  };

  const parseDocx = async (file: File): Promise<string> => {
    const mammoth = await import('mammoth');
    const arrayBuffer = await file.arrayBuffer();
    const result = await mammoth.extractRawText({ arrayBuffer });
    return result.value;
  };

  if (isLoading) {
    return (
      <div className="flex h-[80vh] items-center justify-center">
        <Loader size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 max-w-4xl mx-auto text-center">
        <div className="inline-flex items-center justify-center p-4 bg-red-50 dark:bg-red-950/20 text-red-500 rounded-2xl mb-4">
          <RiFileWarningLine size={32} />
        </div>
        <h2 className="text-xl font-bold text-zinc-900 dark:text-white mb-2">Error Loading Configuration</h2>
        <p className="text-zinc-500 dark:text-zinc-400 mb-6">{error.message || 'Unknown error occurred.'}</p>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-8 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-100 dark:border-zinc-800 pb-6">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-white flex items-center gap-2">
            <RiRobot2Line className="text-primary" />
            AI Configuration
          </h1>
          <p className="text-zinc-500 dark:text-zinc-400 text-sm mt-1">
            Configure system prompt behaviour, auto-order capabilities, and upload knowledge base files.
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={updateMutation.isPending || isParsing}
          className="px-5 py-2.5 bg-primary text-white font-medium rounded-xl hover:bg-primary/95 transition-all shadow-lg shadow-primary/20 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {updateMutation.isPending ? (
            <Loader size="sm" className="text-white" />
          ) : (
            <RiCheckDoubleLine size={18} />
          )}
          Save Configuration
        </button>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

        {/* Left Side: General Settings */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-sm space-y-6">
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-white border-b border-zinc-100 dark:border-zinc-800 pb-3">
              General Config
            </h2>

            {/* AI Enabled Toggle */}
            <div className="flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-zinc-900 dark:text-white block">
                  AI Auto-Responder
                </label>
                <span className="text-xs text-zinc-500 dark:text-zinc-400">
                  Allow AI to automatically chat with customers
                </span>
              </div>
              <button
                onClick={() => setAiEnabled(!aiEnabled)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${aiEnabled ? 'bg-primary' : 'bg-zinc-200 dark:bg-zinc-700'
                  }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${aiEnabled ? 'translate-x-6' : 'translate-x-1'
                    }`}
                />
              </button>
            </div>

            {/* Auto Order Toggle */}
            <div className="flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-zinc-900 dark:text-white block">
                  Auto Order Creation
                </label>
                <span className="text-xs text-zinc-500 dark:text-zinc-400">
                  Allow AI to auto-create order drafts
                </span>
              </div>
              <button
                onClick={() => setAutoOrderEnabled(!autoOrderEnabled)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${autoOrderEnabled ? 'bg-primary' : 'bg-zinc-200 dark:bg-zinc-700'
                  }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${autoOrderEnabled ? 'translate-x-6' : 'translate-x-1'
                    }`}
                />
              </button>
            </div>
          </div>

          {/* Document Upload Card */}
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-sm space-y-4">
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-white border-b border-zinc-100 dark:border-zinc-800 pb-3">
              Knowledge Source
            </h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Upload PDF or DOCX files. They will be parsed to plain text in your browser and appended below.
            </p>

            <div className="relative border-2 border-dashed border-zinc-200 dark:border-zinc-800 hover:border-primary dark:hover:border-primary/50 rounded-xl p-6 text-center cursor-pointer transition-colors group">
              <input
                type="file"
                multiple
                accept=".pdf,.docx"
                onChange={handleFileUpload}
                disabled={isParsing}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
              <div className="flex flex-col items-center justify-center space-y-2">
                {isParsing ? (
                  <>
                    <Loader size="md" className="text-primary animate-spin" />
                    <span className="text-sm text-zinc-500 dark:text-zinc-400">Converting files to text...</span>
                  </>
                ) : (
                  <>
                    <RiUploadCloud2Line size={32} className="text-zinc-400 group-hover:text-primary transition-colors" />
                    <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                      Choose PDF / DOCX files
                    </span>
                    <span className="text-xs text-zinc-500 dark:text-zinc-400">
                      or drag and drop them here
                    </span>
                  </>
                )}
              </div>
            </div>

            {/* Parsed files logs */}
            {parsedFiles.length > 0 && (
              <div className="space-y-2 pt-2">
                <span className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 block">Parsed this session:</span>
                <div className="max-h-36 overflow-y-auto space-y-1.5 no-scrollbar">
                  {parsedFiles.map((file, idx) => (
                    <div key={idx} className="flex items-center justify-between text-xs p-2 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
                      <span className="truncate max-w-[120px] font-medium text-zinc-700 dark:text-zinc-300 flex items-center gap-1">
                        <RiFileTextLine size={14} className="text-primary" />
                        {file.name}
                      </span>
                      <span className="text-zinc-500 dark:text-zinc-400">{file.size}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Side: Prompts and Knowledge Base Area */}
        <div className="lg:col-span-2 space-y-6">

          {/* System Prompt */}
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
              <label className="text-lg font-semibold text-zinc-900 dark:text-white block">
                System Agent Instructions
              </label>
              <span className={`text-xs font-mono tabular-nums ${
                systemPrompt.length > 1800
                  ? systemPrompt.length >= 2000
                    ? 'text-red-500 font-semibold'
                    : 'text-amber-500'
                  : 'text-zinc-400 dark:text-zinc-500'
              }`}>
                {systemPrompt.length} / 2,000
              </span>
            </div>
            <textarea
              rows={6}
              value={systemPrompt}
              maxLength={2000}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="Example: You are a friendly customer agent at Sahayak Shop. Help customers place orders, answer product queries, and resolve shipping issues."
              className="w-full rounded-xl border border-zinc-200 dark:border-zinc-800 bg-transparent p-3 text-sm transition-colors outline-none focus:border-primary focus:ring-1 focus:ring-primary dark:bg-zinc-800/30"
            />
            {systemPrompt.length > 1800 && (
              <p className="text-xs text-amber-500">
                Keep your system prompt concise for best AI performance. Long prompts reduce tool-calling reliability.
              </p>
            )}
          </div>

          {/* Knowledge Base Content */}
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
              <label className="text-lg font-semibold text-zinc-900 dark:text-white">
                Knowledge Base (Text Format)
              </label>
              {knowledgeBase && (
                <button
                  onClick={() => setKnowledgeBase('')}
                  className="text-xs text-red-500 hover:text-red-600 flex items-center gap-1"
                >
                  <RiDeleteBinLine size={14} /> Clear All
                </button>
              )}
            </div>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-[-8px]">
              This is the raw knowledge context injected into the AI agent. You can type directly here or load documents on the left.
            </p>
            <textarea
              rows={12}
              value={knowledgeBase}
              onChange={(e) => setKnowledgeBase(e.target.value)}
              placeholder="Paste or type knowledge base information directly, e.g. FAQ list, return policies, product specifications..."
              className="w-full rounded-xl border border-zinc-200 dark:border-zinc-800 bg-transparent p-3 text-sm font-mono transition-colors outline-none focus:border-primary focus:ring-1 focus:ring-primary dark:bg-zinc-800/30"
            />
          </div>

        </div>
      </div>
    </div>
  );
}
