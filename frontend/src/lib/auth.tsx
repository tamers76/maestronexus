"use client";

/**
 * Client-side auth context. Holds the current user (resolved from /iam/auth/me),
 * exposes login/logout, and RBAC helpers (`hasPermission`, `hasRole`) that mirror
 * the backend (docs/02). Wrap the app in <AuthProvider> (done in root layout).
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  type CurrentUser,
  getMe,
  login as apiLogin,
  logout as apiLogout,
  tokenStore,
} from "@/lib/api";

type AuthState = {
  user: CurrentUser | null;
  loading: boolean;
  signIn: (username: string, password: string, tenantSlug?: string) => Promise<void>;
  signOut: () => void;
  refreshUser: () => Promise<void>;
  hasPermission: (key: string) => boolean;
  hasRole: (...keys: string[]) => boolean;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    if (!tokenStore.access) {
      setUser(null);
      return;
    }
    try {
      setUser(await getMe());
    } catch {
      apiLogout();
      setUser(null);
    }
  }, []);

  // Bootstrap: resolve the session once on mount. All setState calls live in
  // async callbacks (never synchronously in the effect body) per
  // react-hooks/set-state-in-effect.
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        if (tokenStore.access) {
          const me = await getMe();
          if (active) setUser(me);
        }
      } catch {
        apiLogout();
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const signIn = useCallback(
    async (username: string, password: string, tenantSlug?: string) => {
      await apiLogin(username, password, tenantSlug);
      setUser(await getMe());
    },
    [],
  );

  const signOut = useCallback(() => {
    apiLogout();
    setUser(null);
  }, []);

  const hasPermission = useCallback(
    (key: string) =>
      !!user && (user.is_superuser || user.permissions.includes(key)),
    [user],
  );

  const hasRole = useCallback(
    (...keys: string[]) =>
      !!user && (user.is_superuser || keys.some((k) => user.roles.includes(k))),
    [user],
  );

  const value = useMemo<AuthState>(
    () => ({ user, loading, signIn, signOut, refreshUser, hasPermission, hasRole }),
    [user, loading, signIn, signOut, refreshUser, hasPermission, hasRole],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}

/** Maps a user to their primary landing route based on role (docs/03). */
export function primaryRouteFor(user: CurrentUser | null): string {
  if (!user) return "/login";
  if (user.is_superuser || user.roles.some((r) => r.endsWith("admin"))) return "/admin";
  if (user.roles.includes("course_designer") || user.roles.includes("content_creator"))
    return "/admin/courses";
  if (user.roles.includes("teacher") || user.roles.includes("teaching_assistant"))
    return "/teacher";
  if (user.roles.includes("institution_leader")) return "/admin/reports";
  return "/learn";
}
