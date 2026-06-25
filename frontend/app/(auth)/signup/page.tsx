"use client";

import { useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";

/** Maps Supabase English error messages to Korean equivalents. */
function mapAuthError(message: string): string {
  if (message.includes("Invalid login credentials")) {
    return "이메일 또는 비밀번호가 올바르지 않습니다.";
  }
  if (message.includes("Email not confirmed")) {
    return "이메일 인증이 필요합니다. 받은 편지함을 확인해주세요.";
  }
  if (message.includes("User already registered")) {
    return "이미 가입된 이메일입니다.";
  }
  return message;
}

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    // Client-side password confirmation check before calling Supabase.
    if (password !== passwordConfirm) {
      setError("비밀번호가 일치하지 않습니다.");
      return;
    }

    setLoading(true);

    const supabase = createClient();
    const { error } = await supabase.auth.signUp({ email, password });

    if (error) {
      setError(mapAuthError(error.message));
      setLoading(false);
      return;
    }

    setDone(true);
  }

  if (done) {
    return (
      <div
        style={{
          width: 360,
          padding: 32,
          background: "#fff",
          borderRadius: 12,
          boxShadow: "0 2px 8px rgba(0,0,0,.1)",
          textAlign: "center",
        }}
      >
        <h2 style={{ marginBottom: 12 }}>이메일을 확인해주세요</h2>
        <p style={{ fontSize: 14, color: "#6b7280" }}>
          {email}으로 인증 메일을 보냈습니다. 링크를 클릭하면 로그인됩니다.
        </p>
        <Link
          href="/login"
          style={{
            display: "block",
            marginTop: 20,
            color: "#2563eb",
            fontSize: 14,
          }}
        >
          로그인으로 돌아가기
        </Link>
      </div>
    );
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
        회원가입
      </h1>
      <form onSubmit={handleSubmit}>
        <label style={{ display: "block", marginBottom: 4, fontSize: 14 }}>
          이메일
        </label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          style={{
            width: "100%",
            padding: "8px 12px",
            border: "1px solid #d1d5db",
            borderRadius: 6,
            marginBottom: 16,
          }}
        />
        <label style={{ display: "block", marginBottom: 4, fontSize: 14 }}>
          비밀번호 (8자 이상)
        </label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          style={{
            width: "100%",
            padding: "8px 12px",
            border: "1px solid #d1d5db",
            borderRadius: 6,
            marginBottom: 16,
          }}
        />
        <label style={{ display: "block", marginBottom: 4, fontSize: 14 }}>
          비밀번호 확인
        </label>
        <input
          type="password"
          value={passwordConfirm}
          onChange={(e) => setPasswordConfirm(e.target.value)}
          required
          minLength={8}
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
          {loading ? "가입 중…" : "가입하기"}
        </button>
      </form>
      <p style={{ marginTop: 16, fontSize: 14, textAlign: "center" }}>
        이미 계정이 있으신가요?{" "}
        <Link href="/login" style={{ color: "#2563eb" }}>
          로그인
        </Link>
      </p>
    </div>
  );
}
