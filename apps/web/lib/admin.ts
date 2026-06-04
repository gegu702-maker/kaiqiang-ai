import { createClient as createSupabaseClient } from "@supabase/supabase-js";

import type { AdminUser, VideoTask } from "@/lib/types";

export const ADMIN_EMAILS = (process.env.ADMIN_EMAILS ?? "gegu702@gmail.com")
  .split(",")
  .map((email) => email.trim().toLowerCase())
  .filter(Boolean);

export function isAdminEmail(email?: string | null) {
  return Boolean(email && ADMIN_EMAILS.includes(email.toLowerCase()));
}

function createServiceClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !serviceRoleKey) return null;
  return createSupabaseClient(url, serviceRoleKey, {
    auth: {
      persistSession: false,
      autoRefreshToken: false,
    },
  });
}

function startOfTodayIso() {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  return date.toISOString();
}

export type AdminStats = {
  totalUsers: number;
  freeUsers: number;
  businessUsers: number;
  waitlistCount: number | null;
  avatarGenerations: number | null;
  todayGenerations: number | null;
  todayRegistrations: number;
};

export async function getAdminStats(users: AdminUser[], tasks: VideoTask[]): Promise<AdminStats> {
  const today = startOfTodayIso();
  const serviceClient = createServiceClient();
  const freeUsers = users.filter((user) => user.plan === "free").length;
  const businessUsers = users.filter((user) => user.plan === "business").length;

  let waitlistCount: number | null = null;
  let avatarGenerations: number | null = null;
  let todayGenerations: number | null = null;

  if (serviceClient) {
    const [waitlist, avatarTotal, avatarToday] = await Promise.all([
      serviceClient.from("waitlist").select("id", { count: "exact", head: true }),
      serviceClient.from("avatar_tasks").select("id", { count: "exact", head: true }),
      serviceClient.from("avatar_tasks").select("id", { count: "exact", head: true }).gte("created_at", today),
    ]);
    waitlistCount = waitlist.count ?? null;
    avatarGenerations = avatarTotal.count ?? null;
    todayGenerations = avatarToday.count ?? null;
  }

  const fallbackTodayTasks = tasks.filter((task) => new Date(task.created_at).getTime() >= new Date(today).getTime()).length;

  return {
    totalUsers: users.length,
    freeUsers,
    businessUsers,
    waitlistCount,
    avatarGenerations: avatarGenerations ?? tasks.length,
    todayGenerations: todayGenerations ?? fallbackTodayTasks,
    todayRegistrations: users.filter((user) => new Date(user.created_at).getTime() >= new Date(today).getTime()).length,
  };
}
