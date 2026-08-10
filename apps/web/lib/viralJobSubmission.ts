import { ViralJobApiUnavailableError } from "./api";

export type ViralUploadSubmission<Job, Pipeline> =
  | { mode: "async"; job: Job }
  | { mode: "legacy"; pipeline: Pipeline; originalSignal: string };

export async function submitViralUploadWithExplicitFallback<Job, Pipeline>(options: {
  createJob: () => Promise<Job>;
  runLegacyPipeline: () => Promise<Pipeline>;
}): Promise<ViralUploadSubmission<Job, Pipeline>> {
  try {
    return { mode: "async", job: await options.createJob() };
  } catch (error) {
    if (!(error instanceof ViralJobApiUnavailableError)) throw error;
    try {
      return {
        mode: "legacy",
        pipeline: await options.runLegacyPipeline(),
        originalSignal: error.message,
      };
    } catch (fallbackError) {
      const fallbackMessage = fallbackError instanceof Error ? fallbackError.message : "兼容同步接口失败。";
      throw new Error(`${error.message}\n兼容同步接口失败：${fallbackMessage}`);
    }
  }
}
