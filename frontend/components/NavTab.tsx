"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavTabProps {
  href: string;
  label: string;
}

export default function NavTab({ href, label }: NavTabProps) {
  const pathname = usePathname();
  const active = pathname === href || pathname.startsWith(href + "/");

  return (
    <Link
      href={href}
      style={{
        padding: "12px 20px",
        fontSize: 14,
        fontWeight: active ? 600 : 400,
        color: active ? "#2563eb" : "#374151",
        borderBottom: active ? "2px solid #2563eb" : "2px solid transparent",
        textDecoration: "none",
        whiteSpace: "nowrap",
        display: "inline-block",
      }}
    >
      {label}
    </Link>
  );
}
