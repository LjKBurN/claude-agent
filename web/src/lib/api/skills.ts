import { request } from "./client";
import type { SkillsListResponse } from "./types";

export function listSkills() {
  return request<SkillsListResponse>("GET", "/api/skills");
}

export function reloadSkills() {
  return request<{ message: string }>("POST", "/api/skills/reload");
}
