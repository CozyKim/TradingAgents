import ReactMarkdown from "react-markdown";

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
        "min-w-0 break-words [overflow-wrap:anywhere] leading-relaxed space-y-2 [&_h1]:text-sm [&_h1]:font-semibold [&_h2]:text-sm [&_h2]:font-semibold [&_h3]:font-semibold [&_p]:leading-relaxed [&_p]:break-words [&_ul]:list-disc [&_ul]:pl-4 [&_ol]:list-decimal [&_ol]:pl-4 [&_li]:my-0.5 [&_strong]:text-text-1 [&_code]:rounded [&_code]:bg-bg-2 [&_code]:px-1 [&_code]:py-0.5 [&_code]:break-words [&_pre]:overflow-x-auto [&_pre]:whitespace-pre-wrap [&_pre]:break-words [&_pre]:rounded [&_pre]:bg-bg-2 [&_pre]:p-2",
        className,
      )}
    >
      <ReactMarkdown>{text}</ReactMarkdown>
    </div>
  );
}
