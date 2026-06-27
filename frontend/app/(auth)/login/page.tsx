"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";

const USERNAME_REGEX = /^[a-z0-9_]{3,20}$/;
const DOMAIN = "@nutritrack.app";

function toEmail(username: string) {
  return username + DOMAIN;
}

function mapAuthError(message: string): string {
  if (message.includes("Invalid login credentials")) {
    return "아이디 또는 비밀번호가 올바르지 않습니다.";
  }
  if (message.includes("User already registered")) {
    return "이미 가입된 아이디입니다.";
  }
  return message;
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!USERNAME_REGEX.test(username)) {
      setError("아이디는 영문 소문자·숫자·밑줄(_)만 3~20자로 입력하세요.");
      return;
    }

    setLoading(true);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({
      email: toEmail(username),
      password,
    });

    if (error) {
      setError(mapAuthError(error.message));
      setLoading(false);
      return;
    }

    const next = searchParams.get("next") ?? "/log";
    router.push(next);
    router.refresh();
  }

  return (
    <div
      style={{
        width: 360,
        padding: 32,
        background: "#fff",
        borderRadius: 12,
        boxShadow: "0 2px 8px rgba(0,0,0,.1)",
      }}
    >
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 24 }}>
        NutriTrack 로그인
      </h1>
      <form onSubmit={handleSubmit}>
        <label style={{ display: "block", marginBottom: 4, fontSize: 14 }}>
          아이디
        </label>
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value.toLowerCase())}
          required
          placeholder="영문 소문자·숫자·밑줄 3~20자"
          style={{
            width: "100%",
            padding: "8px 12px",
            border: "1px solid #d1d5db",
            borderRadius: 6,
            marginBottom: 16,
          }}
        />
        <label style={{ display: "block", marginBottom: 4, fontSize: 14 }}>
          비밀번호
        </label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          style={{
            width: "100%",
            padding: "8px 12px",
            border: "1px solid #d1d5db",
            borderRadius: 6,
            marginBottom: 24,
          }}
        />
        {error && (
          <p style={{ color: "#ef4444", fontSize: 14, marginBottom: 16 }}>
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={loading}
          style={{
            width: "100%",
            padding: "10px",
            background: "#2563eb",
            color: "#fff",
            border: "none",
            borderRadius: 6,
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "로그인 중…" : "로그인"}
        </button>
      </form>
      <p style={{ marginTop: 16, fontSize: 14, textAlign: "center" }}>
        계정이 없으신가요?{" "}
        <Link href="/signup" style={{ color: "#2563eb" }}>
          회원가입
        </Link>
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
