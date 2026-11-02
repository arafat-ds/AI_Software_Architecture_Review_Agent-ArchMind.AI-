"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";

export default function MarkdownContent({ content }: { content: string }) {
  return (
    <div
      className="
        [&_h1]:text-[#e6edf3] [&_h1]:text-xl [&_h1]:font-bold [&_h1]:mb-3 [&_h1]:mt-6 [&_h1:first-child]:mt-0
        [&_h2]:text-[#e6edf3] [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:mb-2 [&_h2]:mt-5 [&_h2:first-child]:mt-0
        [&_h3]:text-[#cdd9e5] [&_h3]:text-base [&_h3]:font-semibold [&_h3]:mb-2 [&_h3]:mt-4
        [&_h4]:text-[#cdd9e5] [&_h4]:text-sm [&_h4]:font-semibold [&_h4]:mb-1.5 [&_h4]:mt-3
        [&_p]:text-[#8b949e] [&_p]:leading-relaxed [&_p]:mb-3 [&_p]:text-sm
        [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-3 [&_ul]:space-y-1
        [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-3 [&_ol]:space-y-1
        [&_li]:text-[#8b949e] [&_li]:text-sm
        [&_strong]:text-[#cdd9e5] [&_strong]:font-semibold
        [&_em]:text-[#8b949e] [&_em]:italic
        [&_code]:bg-[#1c2128] [&_code]:text-[#79c0ff] [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-xs [&_code]:font-mono
        [&_pre]:bg-[#1c2128] [&_pre]:rounded-lg [&_pre]:p-4 [&_pre]:overflow-x-auto [&_pre]:mb-4 [&_pre]:border [&_pre]:border-[#30363d]
        [&_pre_code]:bg-transparent [&_pre_code]:text-inherit [&_pre_code]:p-0 [&_pre_code]:text-xs
        [&_blockquote]:border-l-2 [&_blockquote]:border-[#388bfd] [&_blockquote]:pl-4 [&_blockquote]:text-[#8b949e] [&_blockquote]:italic [&_blockquote]:mb-3
        [&_hr]:border-[#30363d] [&_hr]:my-4
        [&_table]:w-full [&_table]:border-collapse [&_table]:mb-4 [&_table]:text-sm
        [&_thead_tr]:border-b [&_thead_tr]:border-[#30363d]
        [&_th]:text-[#cdd9e5] [&_th]:text-left [&_th]:py-2 [&_th]:px-3 [&_th]:font-semibold
        [&_td]:text-[#8b949e] [&_td]:py-2 [&_td]:px-3 [&_td]:border-b [&_td]:border-[#21262d]
        [&_a]:text-[#58a6ff] [&_a]:underline [&_a]:underline-offset-2
      "
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
