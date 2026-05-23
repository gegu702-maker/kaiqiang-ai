"use client";

import { ChangeEvent, useEffect, useRef, useState } from "react";
import { FileAudio, Trash2, UploadCloud } from "lucide-react";
import { motion } from "framer-motion";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

export function VoiceUpload() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState("");
  const [progress, setProgress] = useState(0);
  const [inputKey, setInputKey] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!fileName || progress >= 100) return;

    const timer = window.setInterval(() => {
      setProgress((current) => Math.min(100, current + 18));
    }, 120);

    return () => window.clearInterval(timer);
  }, [fileName, progress]);

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    setError("");
    if (!file) return;

    const validExtension = /\.(mp3|wav|m4a)$/i.test(file.name);
    const validType = [
      "audio/mpeg",
      "audio/mp3",
      "audio/wav",
      "audio/x-wav",
      "audio/wave",
      "audio/m4a",
      "audio/x-m4a",
      "audio/mp4",
    ].includes(file.type);
    if (!validType && !validExtension) {
      setError("支持 mp3 / wav / m4a 格式");
      event.target.value = "";
      return;
    }

    if (file.size > 20 * 1024 * 1024) {
      setError("声音文件最大支持 20MB。");
      event.target.value = "";
      return;
    }

    setFileName(file.name);
    setProgress(12);
  }

  function clearFile() {
    setFileName("");
    setProgress(0);
    setError("");
    setInputKey((key) => key + 1);
  }

  return (
    <section className="space-y-2">
      <div>
        <h3 className="text-sm font-medium text-slate-200">参考语音</h3>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-lg border border-dashed border-white/15 bg-white/[0.04] p-4"
      >
        <input
          key={inputKey}
          ref={inputRef}
          required
          type="file"
          name="voice"
          accept="audio/mpeg,audio/mp3,audio/wav,audio/x-wav,audio/m4a,audio/x-m4a,audio/mp4,.mp3,.wav,.m4a"
          onChange={handleChange}
          className="sr-only"
        />

        {fileName ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-3">
                <span className="grid size-10 place-items-center rounded-md bg-cyan/10 text-cyan">
                  <FileAudio size={18} />
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-white">{fileName}</p>
                  <p className="text-xs text-slate-500">{progress < 100 ? "正在准备上传" : "文件已就绪"}</p>
                </div>
              </div>
              <Button type="button" variant="ghost" size="icon" onClick={clearFile} aria-label="删除声音文件">
                <Trash2 size={16} />
              </Button>
            </div>
            <Progress value={progress} />
          </div>
        ) : (
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="flex w-full flex-col items-center justify-center gap-2 rounded-md border border-white/10 bg-ink/40 px-4 py-5 text-center transition hover:border-cyan/40 hover:bg-cyan/5"
          >
            <span className="grid size-11 place-items-center rounded-lg bg-cyan/10 text-cyan">
              <UploadCloud size={20} />
            </span>
            <span className="text-sm font-medium text-white">上传声音文件</span>
            <span className="text-xs text-slate-500">MP3 / WAV / M4A</span>
          </button>
        )}
        {error ? <p className="mt-3 text-xs text-rose-200">{error}</p> : null}
      </motion.div>
    </section>
  );
}
