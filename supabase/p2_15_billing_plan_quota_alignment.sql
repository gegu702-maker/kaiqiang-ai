-- P2.15-C: Align production billing plan quotas with public pricing.
-- Safe/idempotent migration.
-- Expected:
--   plus monthly_quota = 1000
--   pro  monthly_quota = 3000
-- This migration only updates public.plans rows by code.
-- It does not touch profiles, orders, subscriptions, usage_logs, user_quotas, Stripe, or billing history.

update public.plans
set monthly_quota = case code
  when 'plus' then 1000
  when 'pro' then 3000
end,
updated_at = now()
where code in ('plus', 'pro')
  and (
    (code = 'plus' and monthly_quota is distinct from 1000)
    or
    (code = 'pro' and monthly_quota is distinct from 3000)
  );

-- Verification query to run manually after migration:
-- select code, name, monthly_quota, updated_at
-- from public.plans
-- where code in ('plus', 'pro')
-- order by code;
