"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { Loading } from "@/components/Loading";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading, checkAuth } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      void checkAuth().then((me) => {
        if (!me) router.replace("/login");
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, user]);

  if (!user) {
    return <Loading label="Checking your session…" />;
  }
  return <>{children}</>;
}

export function useRedirectIfAuthed() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  useEffect(() => {
    if (!loading && user) {
      const next = pathname === "/login" || pathname === "/signup" ? "/dashboard" : "/dashboard";
      router.replace(next);
    }
  }, [user, loading, router, pathname]);
  return { loading };
}