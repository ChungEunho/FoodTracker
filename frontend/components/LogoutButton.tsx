"use client";

import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export default function LogoutButton() {
  const router = useRouter();

  async function handleLogout() {
    const supabase = createClient();

    // 1. Grab the current session so we can authenticate the backend call.
    const {
      data: { session },
    } = await supabase.auth.getSession();

    // 2. Client-side signOut: revokes the refresh token on Supabase's servers
    //    and clears the local session cookies.
    await supabase.auth.signOut();

    // 3. Backend logout: revokes ALL sessions for this user (other devices/tabs)
    //    via the Supabase Admin API. Best-effort — we redirect regardless.
    if (session?.access_token) {
      try {
        await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/logout`, {
          method: "POST",
          headers: { Authorization: `Bearer ${session.access_token}` },
        });
      } catch {
        // Network error — local session is already cleared; proceed to login.
      }
    }

    router.push("/login");
    router.refresh();
  }

  return (
    <button
      onClick={handleLogout}
      style={{
        padding: "6px 14px",
        background: "#f3f4f6",
        border: "1px solid #d1d5db",
        borderRadius: 6,
        cursor: "pointer",
        fontSize: 14,
      }}
    >
      로그아웃
    </button>
  );
}
