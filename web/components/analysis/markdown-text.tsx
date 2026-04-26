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
          "whitespace-pre-wrap font-sans leading-relaxed",
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
        "leading-relaxed space-y-2 [&_h1]:text-sm [&_h1]:font-semibold [&_h2]:text-sm [&_h2]:font-semibold [&_h3]:font-semibold [&_p]:leading-relaxed [&_ul]:list-disc [&_ul]:pl-4 [&_ol]:list-decimal [&_ol]:pl-4 [&_li]:my-0.5 [&_strong]:text-text-1 [&_code]:rounded [&_code]:bg-bg-2 [&_code]:px-1 [&_code]:py-0.5 [&_pre]:overflow-x-auto [&_pre]:rounded [&_pre]:bg-bg-2 [&_pre]:p-2",
        className,
      )}
    >
      <ReactMarkdown>{text}</ReactMarkdown>
    </div>
  );
}
