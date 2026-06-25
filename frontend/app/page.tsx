import { redirect } from "next/navigation";

export default function RootPage() {
  // Middleware decides the real destination: authenticated users land on /log,
  // unauthenticated users are redirected to /login.
  redirect("/log");
}
