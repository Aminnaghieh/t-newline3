"use client";
import { create } from "zustand";

export type Section =
  | "dashboard"
  | "agent"
  | "projects"
  | "deploy"
  | "audit"
  | "settings";

interface AppState {
  section: Section;
  selectedProject: string | null;
  navigate: (s: Section, project?: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  section: "dashboard",
  selectedProject: null,
  navigate: (s, project = null) => set({ section: s, selectedProject: project }),
}));
