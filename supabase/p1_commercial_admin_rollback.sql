-- Rollback for p1_commercial_admin_migration.sql.
-- This keeps existing customer/order data and removes only P1 admin additions.

drop policy if exists "Anyone can read active plans" on public.plans;
drop policy if exists "Service role can manage plans" on public.plans;
drop table if exists public.plans;

drop index if exists public.payments_user_created_idx;
drop index if exists public.subscriptions_user_created_idx;
drop index if exists public.user_quotas_reset_month_idx;

alter table if exists public.subscriptions
drop column if exists cancel_at_period_end;

alter table if exists public.subscriptions
drop column if exists provider_subscription_id;

alter table if exists public.profiles
drop column if exists role;

notify pgrst, 'reload schema';
