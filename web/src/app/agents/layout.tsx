"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/layout/theme-toggle";

export default function AgentsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-3">
          <Link href="/chat">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <h1 className="text-sm font-semibold">Agent 管理</h1>
        </div>
        <ThemeToggle />
      </header>
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
