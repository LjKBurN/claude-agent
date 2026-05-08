"use client";

import { type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { CodeBlock } from "./code-block";
import type { ComponentPropsWithoutRef } from "react";

/** 从 React children 中递归提取纯文本（rehype-highlight 会将代码转为 span 元素）。 */
function extractTextFromChildren(children: ReactNode): string {
  if (typeof children === "string") return children;
  if (typeof children === "number") return String(children);
  if (!children) return "";
  if (Array.isArray(children)) return children.map(extractTextFromChildren).join("");
  if (typeof children === "object" && "props" in children) {
    return extractTextFromChildren((children as { props: { children?: ReactNode } }).props.children);
  }
  return "";
}

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          pre({ children, ...props }) {
            return <pre {...props}>{children}</pre>;
          },
          code({ className, children, ...props }: ComponentPropsWithoutRef<"code"> & { className?: string }) {
            const match = /language-(\w+)/.exec(className || "");
            const codeStr = extractTextFromChildren(children).replace(/\n$/, "");

            // Block code with language tag
            if (match) {
              return <CodeBlock language={match[1]} code={codeStr} />;
            }

            // Inline code
            return (
              <code
                className="rounded bg-muted px-1.5 py-0.5 text-sm font-mono"
                {...props}
              >
                {children}
              </code>
            );
          },
          p({ children }) {
            return <p className="mb-3 last:mb-0 leading-7">{children}</p>;
          },
          ul({ children }) {
            return <ul className="mb-3 list-disc pl-6 space-y-1">{children}</ul>;
          },
          ol({ children }) {
            return <ol className="mb-3 list-decimal pl-6 space-y-1">{children}</ol>;
          },
          li({ children }) {
            return <li className="leading-7">{children}</li>;
          },
          h1({ children }) {
            return <h1 className="text-2xl font-bold mb-3 mt-4 first:mt-0">{children}</h1>;
          },
          h2({ children }) {
            return <h2 className="text-xl font-bold mb-2 mt-4 first:mt-0">{children}</h2>;
          },
          h3({ children }) {
            return <h3 className="text-lg font-semibold mb-2 mt-3 first:mt-0">{children}</h3>;
          },
          blockquote({ children }) {
            return (
              <blockquote className="border-l-4 border-muted-foreground/30 pl-4 italic text-muted-foreground mb-3">
                {children}
              </blockquote>
            );
          },
          a({ href, children }) {
            return (
              <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary underline underline-offset-4 hover:text-primary/80">
                {children}
              </a>
            );
          },
          table({ children }) {
            return (
              <div className="mb-3 overflow-x-auto">
                <table className="w-full border-collapse border border-border text-sm">
                  {children}
                </table>
              </div>
            );
          },
          th({ children }) {
            return <th className="border border-border px-3 py-2 bg-muted font-medium text-left">{children}</th>;
          },
          td({ children }) {
            return <td className="border border-border px-3 py-2">{children}</td>;
          },
          hr() {
            return <hr className="my-4 border-border" />;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
