"use client";

/**
 * Lightweight theme context (dark/light) for the Curriculum Intelligence UI.
 * Persists to localStorage and toggles the `dark` class on <html>. Defaults to
 * the futuristic dark look. A blocking inline script (see ThemeScript) applies
 * the stored choice before paint to avoid a flash.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";

export type Theme = "dark" | "light";

const STORAGE_KEY = "maestro-theme";
const DEFAULT_THEME: Theme = "dark";

type ThemeState = {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (t: Theme) => void;
};

const ThemeContext = createContext<ThemeState | null>(null);

/** Inline script that runs before hydration to set the initial theme class. */
export function ThemeScript() {
  const code = `(function(){try{var t=localStorage.getItem('${STORAGE_KEY}')||'${DEFAULT_THEME}';var r=document.documentElement;r.classList.remove('light','dark');r.classList.add(t);r.style.colorScheme=t;}catch(e){document.documentElement.classList.add('${DEFAULT_THEME}');}})();`;
  return <script dangerouslySetInnerHTML={{ __html: code }} />;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // Lazily resolve the stored theme on the client; the blocking ThemeScript has
  // already applied the matching class to <html> before paint.
  const [theme, setThemeState] = useState<Theme>(() => {
    if (typeof window === "undefined") return DEFAULT_THEME;
    return (localStorage.getItem(STORAGE_KEY) as Theme | null) ?? DEFAULT_THEME;
  });

  const apply = useCallback((t: Theme) => {
    const root = document.documentElement;
    root.classList.remove("light", "dark");
    root.classList.add(t);
    root.style.colorScheme = t;
    localStorage.setItem(STORAGE_KEY, t);
  }, []);

  const setTheme = useCallback(
    (t: Theme) => {
      setThemeState(t);
      apply(t);
    },
    [apply],
  );

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => {
      const next: Theme = prev === "dark" ? "light" : "dark";
      apply(next);
      return next;
    });
  }, [apply]);

  const value = useMemo<ThemeState>(
    () => ({ theme, toggleTheme, setTheme }),
    [theme, toggleTheme, setTheme],
  );

  return <ThemeContext value={value}>{children}</ThemeContext>;
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within <ThemeProvider>");
  return ctx;
}
