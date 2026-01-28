import React, { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Database, Download, RefreshCw, ExternalLink } from 'lucide-react';

export default function DataTab() {
  const [markdown, setMarkdown] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('/data/DATABASE.md')
      .then((res) => {
        if (!res.ok) throw new Error('Failed to fetch documentation');
        return res.text();
      })
      .then((text) => {
        setMarkdown(text);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex items-center gap-3 text-slate-500">
          <RefreshCw className="w-5 h-5 animate-spin" />
          Loading documentation...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-red-500">Error: {error}</div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto bg-slate-50">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-white/95 backdrop-blur-xl border-b border-slate-200 px-8 py-4">
        <div className="flex items-center justify-between max-w-4xl mx-auto">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center">
              <Database className="w-5 h-5 text-emerald-600" />
            </div>
            <div>
              <h2 className="text-lg font-medium text-slate-800">Data Documentation</h2>
              <p className="text-xs text-slate-500">Comprehensive guide to the dataset</p>
            </div>
          </div>
          <a
            href="/data/DATABASE.md"
            download
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-sm text-slate-600 transition-colors border border-slate-200"
          >
            <Download className="w-4 h-4" />
            Download MD
          </a>
        </div>
      </div>

      {/* Markdown Content */}
      <div className="max-w-4xl mx-auto px-8 py-8">
        <article className="prose prose-slate max-w-none
          prose-headings:font-medium prose-headings:text-slate-800
          prose-h1:text-3xl prose-h1:border-b prose-h1:border-slate-200 prose-h1:pb-4 prose-h1:mb-6
          prose-h2:text-2xl prose-h2:mt-10 prose-h2:mb-4 prose-h2:text-emerald-700
          prose-h3:text-xl prose-h3:mt-8 prose-h3:mb-3 prose-h3:text-slate-700
          prose-h4:text-lg prose-h4:text-slate-600
          prose-p:text-slate-600 prose-p:leading-relaxed
          prose-a:text-emerald-600 prose-a:no-underline hover:prose-a:underline
          prose-strong:text-slate-800 prose-strong:font-semibold
          prose-code:text-emerald-700 prose-code:bg-emerald-50 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-sm prose-code:font-mono prose-code:before:content-[''] prose-code:after:content-['']
          prose-pre:bg-slate-100 prose-pre:border prose-pre:border-slate-200 prose-pre:rounded-xl
          prose-blockquote:border-l-emerald-500 prose-blockquote:bg-emerald-50/50 prose-blockquote:rounded-r-xl prose-blockquote:py-1
          prose-ul:text-slate-600 prose-ol:text-slate-600
          prose-li:marker:text-emerald-500
          prose-hr:border-slate-200
          prose-table:border-collapse prose-table:w-full
          prose-th:bg-slate-100 prose-th:text-slate-700 prose-th:font-medium prose-th:px-4 prose-th:py-3 prose-th:text-left prose-th:border prose-th:border-slate-200
          prose-td:px-4 prose-td:py-3 prose-td:border prose-td:border-slate-200 prose-td:text-slate-600
          prose-tr:even:bg-slate-50
        ">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              // Custom table wrapper for horizontal scrolling
              table: ({ node, ...props }) => (
                <div className="overflow-x-auto rounded-xl border border-slate-200 my-6 bg-white">
                  <table {...props} className="min-w-full" />
                </div>
              ),
              // External link icon for links
              a: ({ node, href, children, ...props }) => {
                const isExternal = href?.startsWith('http');
                return (
                  <a
                    href={href}
                    {...props}
                    target={isExternal ? '_blank' : undefined}
                    rel={isExternal ? 'noopener noreferrer' : undefined}
                    className="inline-flex items-center gap-1"
                  >
                    {children}
                    {isExternal && <ExternalLink className="w-3 h-3" />}
                  </a>
                );
              },
              // Better code block styling
              pre: ({ node, ...props }) => (
                <pre {...props} className="overflow-x-auto" />
              ),
            }}
          >
            {markdown}
          </ReactMarkdown>
        </article>
      </div>
    </div>
  );
}
