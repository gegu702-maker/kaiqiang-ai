"use client";

import { useEffect, useRef, useState } from "react";
import { Download, Subtitles } from "lucide-react";

import { Button } from "@/components/ui/button";

export function VideoPlayer({
  url,
  subtitleUrl,
  script,
  showSubtitleTools = false,
}: {
  url: string | null;
  subtitleUrl?: string | null;
  script?: string;
  showSubtitleTools?: boolean;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [subtitlesEnabled, setSubtitlesEnabled] = useState(Boolean(subtitleUrl));

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    Array.from(video.textTracks).forEach((track) => {
      track.mode = subtitlesEnabled ? "showing" : "hidden";
    });
  }, [subtitlesEnabled, subtitleUrl]);

  if (!url) {
    return (
      <div className="grid aspect-video place-items-center rounded-lg border border-white/10 bg-ink/60 text-sm text-slate-500">
        最终视频尚未上传
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="overflow-hidden rounded-lg border border-white/10 bg-black shadow-glow">
        <video ref={videoRef} controls src={url} className="aspect-video w-full bg-black">
          {subtitleUrl ? (
            <track src={subtitleUrl} kind="subtitles" srcLang="zh" label="Script subtitles" default />
          ) : null}
        </video>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button asChild variant="outline">
          <a href={url} target="_blank" rel="noreferrer" download>
            <Download size={16} />
            下载 MP4
          </a>
        </Button>
        {showSubtitleTools && subtitleUrl ? (
          <Button type="button" variant={subtitlesEnabled ? "default" : "outline"} onClick={() => setSubtitlesEnabled((value) => !value)}>
            <Subtitles size={16} />
            {subtitlesEnabled ? "字幕开启" : "字幕关闭"}
          </Button>
        ) : null}
      </div>
      {showSubtitleTools ? (
        <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-200">
            <Subtitles size={16} />
            字幕预览
          </div>
          {subtitleUrl ? (
            <p className="line-clamp-5 text-sm leading-7 text-slate-300">{script}</p>
          ) : (
            <p className="text-sm text-slate-500">字幕尚未生成。管理员上传最终 MP4 后会自动生成。</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
