import assert from "node:assert/strict";
import test from "node:test";

import { createAvatarTemplates } from "../avatarTemplates";
import { createCustomerCases } from "../cases";
import {
  allowExternalMediaUrl,
  isPreviewEnvironment,
  PRODUCTION_SUPABASE_MEDIA_ORIGIN,
} from "../runtimeEnvironment";

const productionMediaUrl = `${PRODUCTION_SUPABASE_MEDIA_ORIGIN}/storage/v1/object/public/videos/example.mp4`;

test("environment flag uses the explicit public app environment", () => {
  assert.equal(
    isPreviewEnvironment,
    process.env.NEXT_PUBLIC_APP_ENVIRONMENT === "preview",
  );
});

test("media filter keeps non-preview URLs unchanged", () => {
  assert.equal(allowExternalMediaUrl(productionMediaUrl, false), productionMediaUrl);
});

test("media filter fails closed for Production Supabase in Preview", () => {
  assert.equal(allowExternalMediaUrl(productionMediaUrl, true), undefined);
});

test("media filter allows local and secure non-Production media in Preview", () => {
  assert.equal(allowExternalMediaUrl("/avatars/local.png", true), "/avatars/local.png");
  assert.equal(
    allowExternalMediaUrl("https://preview-assets.example/template.mp4", true),
    "https://preview-assets.example/template.mp4",
  );
});

test("media filter rejects malformed and unsafe external URLs in Preview", () => {
  assert.equal(allowExternalMediaUrl("not a valid URL", true), undefined);
  assert.equal(allowExternalMediaUrl("//production.example/template.mp4", true), undefined);
  assert.equal(allowExternalMediaUrl("http://preview-assets.example/template.mp4", true), undefined);
  assert.equal(allowExternalMediaUrl("data:video/mp4;base64,AAAA", true), undefined);
  assert.equal(allowExternalMediaUrl("blob:https://preview.example/id", true), undefined);
});

test("Preview avatar templates keep local posters without Production videos", () => {
  const templates = createAvatarTemplates({
    previewEnvironment: true,
    businessFemalePreviewVideoUrl: productionMediaUrl,
    businessMalePreviewVideoUrl: productionMediaUrl,
  });

  assert.equal(templates.length, 2);
  assert.ok(templates.every((template) => template.preview_video_url === undefined));
  assert.ok(templates.every((template) => template.avatar_image.startsWith("/avatars/")));
});

test("non-Preview avatar templates preserve configured videos", () => {
  const templates = createAvatarTemplates({
    previewEnvironment: false,
    businessFemalePreviewVideoUrl: productionMediaUrl,
    businessMalePreviewVideoUrl: productionMediaUrl,
  });

  assert.ok(templates.every((template) => template.preview_video_url === productionMediaUrl));
});

test("Preview homepage cases retain local thumbnails without Production videos", () => {
  const cases = createCustomerCases({ previewEnvironment: true });

  assert.equal(cases.length, 4);
  assert.ok(cases.every((item) => item.videoUrl === undefined));
  assert.ok(cases.every((item) => item.thumbnailUrl.startsWith("/")));
});

test("non-Preview homepage cases preserve Production demonstration videos", () => {
  const cases = createCustomerCases({ previewEnvironment: false });

  assert.equal(cases.length, 4);
  assert.ok(
    cases.every((item) => item.videoUrl?.startsWith(PRODUCTION_SUPABASE_MEDIA_ORIGIN)),
  );
});
