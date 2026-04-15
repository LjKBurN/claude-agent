"use client";

import useSWR from "swr";
import { listSkills, reloadSkills } from "@/lib/api/skills";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { RefreshCw, Sparkles } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

export function SkillsPanel() {
  const { data, isLoading, mutate } = useSWR("/api/skills", listSkills);
  const [reloading, setReloading] = useState(false);

  const handleReload = async () => {
    setReloading(true);
    try {
      await reloadSkills();
      mutate();
      toast.success("Skills 已重新加载");
    } catch {
      toast.error("重新加载失败");
    } finally {
      setReloading(false);
    }
  };

  return (
    <div className="space-y-3 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold flex items-center gap-1.5">
          <Sparkles className="h-4 w-4" />
          Skills
        </h2>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleReload} disabled={reloading}>
          <RefreshCw className={`h-3.5 w-3.5 ${reloading ? "animate-spin" : ""}`} />
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : !data?.skills.length ? (
        <div className="text-center text-xs text-muted-foreground py-4">
          暂无 Skills
        </div>
      ) : (
        <div className="space-y-2">
          {data.skills.map((skill) => (
            <Card key={skill.name} className="py-2">
              <CardHeader className="px-3 py-1">
                <CardTitle className="text-sm flex items-center gap-2">
                  {skill.name}
                  <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                    v{skill.version}
                  </Badge>
                  {skill.source && (
                    <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                      {skill.source}
                    </Badge>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="px-3 py-1">
                <p className="text-xs text-muted-foreground">{skill.description}</p>
                {skill.allowed_tools.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {skill.allowed_tools.map((tool) => (
                      <Badge key={tool} variant="outline" className="text-[10px] px-1 py-0">
                        {tool}
                      </Badge>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
