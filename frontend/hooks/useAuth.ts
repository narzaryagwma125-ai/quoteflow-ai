"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Me, Plan } from "@/types";

interface AuthState {
  user: Me | null;
  loading: boolean;
  error: string | null;
  checkAuth: () => Promise<Me | null>;
  logout: () => Promise<void>;
}

export function useAuth(): AuthState {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const checkAuth = useCallback(async (): Promise<Me | null> => {
    try {
      const me = await api<Me>("/me");
      setUser(me);
      setError(null);
      return me;
    } catch (err) {
      if (err instanceof Error && (err as { status?: number }).status === 401) {
        setUser(null);
      } else {
        setError(err instanceof Error ? err.message : "Unable to reach the server.");
      }
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api<{ message: string }>("/auth/logout", { method: "POST" });
    } catch {
      // ignore
    }
    setUser(null);
    window.location.href = "/login";
  }, []);

  useEffect(() => {
    void checkAuth();
  }, [checkAuth]);

  return { user, loading, error, checkAuth, logout };
}

export function currentPlan(user: Me | null): Plan {
  return user?.plan ?? "free";
}