import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import LogoutButton from "@/components/LogoutButton";
import NavTab from "@/components/NavTab";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Defense-in-depth: middleware is the primary guard, but we re-verify the
  // session server-side here so no dashboard page renders without a valid user,
  // even if the matcher ever misses a path.
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  const tabs = [
    { href: "/log",     label: "식사 기록" },
    { href: "/daily",   label: "일별 조회" },
    { href: "/summary", label: "기간 요약" },
    { href: "/records", label: "기록 관리" },
  ];

  return (
    <div>
      <header
        style={{
          background: "#fff",
          borderBottom: "1px solid #e5e7eb",
          padding: "12px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <span style={{ fontWeight: 700, fontSize: 18 }}>NutriTrack</span>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ fontSize: 14, color: "#6b7280" }}>{user.email}</span>
          <LogoutButton />
        </div>
      </header>
      <nav
        style={{
          background: "#fff",
          borderBottom: "1px solid #e5e7eb",
          display: "flex",
          gap: 0,
        }}
      >
        {tabs.map(({ href, label }) => (
          <NavTab key={href} href={href} label={label} />
        ))}
      </nav>
      <main style={{ padding: 24 }}>{children}</main>
    </div>
  );
}
