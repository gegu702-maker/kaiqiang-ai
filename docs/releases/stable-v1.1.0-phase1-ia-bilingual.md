# stable-v1.1.0-phase1-ia-bilingual

## Production

- Project: kaiqiang-ai
- Domain: https://kaiqiang.ai
- Commit: 147cb253d9260d3f11ed6a21e156a7fc0f8e85ee
- Deployment ID: dpl_9V2UBugQj1snsk9bUsCgqrkpm7Y6
- Clean branch: codex/phase1-ia-bilingual-clean

## Scope

This stable version locks the Phase 1 IA and bilingual cleanup release.

## Fixes

- Restored Pricing to four tiers: Free / Plus / Pro / Business.
- Removed Creator from Pricing.
- Removed old commercial wording such as AI digital human SaaS package language.
- Removed exposed supplier wording from user-facing Pricing and Studio surfaces.
- Consolidated the main Studio flow as Link -> Analyze -> Rewrite -> Avatar -> Export.
- Kept Studio as the primary workspace while preserving /studio/avatar and /studio/viral-analyzer routes.
- Consolidated the main navigation to: 首页 / 套餐 / 模板 / Studio / 账户.
- Removed 爆款拆解, 数字人工作台, Viral Analyzer, and Avatar Studio from the main navigation.
- Added shared bilingual copy dictionaries for navigation, pricing, and studio IA.

## Verification

- Pricing verified as Free / Plus / Pro / Business.
- Studio verified with Link -> Analyze -> Rewrite -> Avatar -> Export.
- Main navigation verified as 首页 / 套餐 / 模板 / Studio / 账户.
- Clean branch deployment verified without billing/API/admin dirty changes.
- Chinese and English switching verified as normal.

## Deployment Safety

This release was deployed from the clean branch `codex/phase1-ia-bilingual-clean`.

The deployment did not include the unrelated billing/API/admin dirty changes from `codex/p1-commercial-admin`.

Included web IA/bilingual files only:

- apps/web/app/account/page.tsx
- apps/web/app/pricing/page.tsx
- apps/web/app/studio/page.tsx
- apps/web/app/studio/templates/page.tsx
- apps/web/components/PlanCheckoutButton.tsx
- apps/web/components/SiteFooter.tsx
- apps/web/components/SiteHeader.tsx
- apps/web/components/StudioNavigation.tsx
- apps/web/components/StudioWorkspace.tsx
- apps/web/components/TaskForm.tsx
- apps/web/components/ViralAnalyzerClient.tsx
- apps/web/components/VoiceCloneManager.tsx
- apps/web/lib/i18n/navigation.ts
- apps/web/lib/i18n/pricing.ts
- apps/web/lib/i18n/studio.ts
- apps/web/lib/tts.ts
