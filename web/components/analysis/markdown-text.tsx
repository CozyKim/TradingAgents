import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

export type TextRenderMode = "markdown" | "plain";

export function MarkdownText({
  text,
  mode = "markdown",
  className,
}: {
  text: string;
  mode?: TextRenderMode;
  className?: string;
}) {
  if (mode === "plain") {
    return (
      <pre
        className={cn(
          "min-w-0 whitespace-pre-wrap break-words [overflow-wrap:anywhere] font-sans leading-relaxed",
          className,
        )}
      >
        {text}
      </pre>
    );
  }

  return (
    <div
      className={cn(
        "min-w-0 break-words [overflow-wrap:anywhere] leading-relaxed space-y-2",
        // Headings / paragraphs / lists
        "[&_h1]:text-sm [&_h1]:font-semibold [&_h2]:text-sm [&_h2]:font-semibold [&_h3]:font-semibold",
        "[&_p]:leading-relaxed [&_p]:break-words",
        "[&_ul]:list-disc [&_ul]:pl-4 [&_ol]:list-decimal [&_ol]:pl-4 [&_li]:my-0.5",
        // Inline emphasis + code blocks
        "[&_strong]:text-text-1",
        "[&_code]:rounded [&_code]:bg-bg-2 [&_code]:px-1 [&_code]:py-0.5 [&_code]:break-words",
        "[&_pre]:overflow-x-auto [&_pre]:whitespace-pre-wrap [&_pre]:break-words [&_pre]:rounded [&_pre]:bg-bg-2 [&_pre]:p-2",
        // GFM tables — without these the sector analysis market-size /
        // CAGR / share tables collapsed to a single line of "| ... |" text.
        "[&_table]:my-3 [&_table]:w-full [&_table]:border-collapse [&_table]:overflow-x-auto [&_table]:text-sm",
        "[&_th]:border [&_th]:border-border-1 [&_th]:bg-bg-2 [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_th]:font-semibold",
        "[&_td]:border [&_td]:border-border-1 [&_td]:px-3 [&_td]:py-2 [&_td]:align-top",
        // GFM blockquotes (LLM uses these heavily for definitions / notes)
        "[&_blockquote]:border-l-4 [&_blockquote]:border-border-2 [&_blockquote]:bg-bg-2 [&_blockquote]:px-3 [&_blockquote]:py-2 [&_blockquote]:text-text-2",
        className,
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}
