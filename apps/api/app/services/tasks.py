import logging
from typing import Any

from postgrest.exceptions import APIError
from supabase import Client

from app.models.video_task import TaskStatus
from app.services.content_ai import generate_commerce_package


TABLE = "video_tasks"
logger = logging.getLogger(__name__)


def create_task(
    supabase: Client,
    *,
    user_id: str,
    user_email: str,
    product_name: str,
    script: str,
    product_highlights: str,
    target_audience: str,
    video_style: str,
    use_digital_human: bool,
    ai_package: dict[str, Any],
    language: str,
    image_url: str,
    personal_image_url: str | None,
    avatar_id: str,
    voice_url: str,
    voice_clone_id: str | None,
    use_cloned_voice: bool,
    tts_language: str,
    tts_voice_name: str,
) -> dict[str, Any]:
    payload = {
        "user_id": user_id,
        "user_email": user_email,
        "product_name": product_name,
        "script": script,
        "product_highlights": product_highlights,
        "target_audience": target_audience,
        "video_style": video_style,
        "use_digital_human": use_digital_human,
        "production_mode": "semi_auto",
        "language": language,
        "image_url": image_url,
        "personal_image_url": personal_image_url,
        "avatar_id": avatar_id,
        "voice_url": voice_url,
        "voice_clone_id": voice_clone_id,
        "use_cloned_voice": use_cloned_voice,
        "tts_language": tts_language,
        "tts_voice_name": tts_voice_name,
        "admin_notes": "",
        "subtitle_status": "pending",
        "cosyvoice_status": "pending",
        "selling_points": ai_package["selling_points"],
        "hook": ai_package["hook"],
        "shot_list": ai_package["shot_list"],
        "title_options": ai_package["title_options"],
        "caption": ai_package["caption"],
        "cover_text": ai_package["cover_text"],
        "cover_prompt": ai_package["cover_prompt"],
        "hashtags": ai_package["hashtags"],
        "comment_prompt": ai_package["comment_prompt"],
        "closing_cta": ai_package["closing_cta"],
        "admin_workflow": ai_package["admin_workflow"],
        "status": TaskStatus.waiting.value,
    }
    used_fallback = False
    try:
        result = _insert_task_payload(supabase, payload)
    except APIError as error:
        message = str(error)
        if "schema cache" not in message and "PGRST204" not in message:
            raise
        # Supabase/PostgREST can keep a stale schema cache right after adding
        # optional MVP columns. Keep task submission working with the stable
        # base fields; the optional fields have defaults in the API model.
        fallback_payload = {
            key: value
            for key, value in payload.items()
            if key
            not in {
                "admin_notes",
                "subtitle_status",
                "cosyvoice_status",
                "personal_image_url",
                "product_highlights",
                "target_audience",
                "video_style",
                "use_digital_human",
                "production_mode",
                "selling_points",
                "hook",
                "shot_list",
                "title_options",
                "caption",
                "cover_text",
                "cover_prompt",
                "hashtags",
                "comment_prompt",
                "closing_cta",
                "admin_workflow",
                "user_id",
                "voice_clone_id",
                "use_cloned_voice",
            }
        }
        result = _insert_task_payload(supabase, fallback_payload)
        used_fallback = True
    task = result.data[0]
    try:
        queue_insert = supabase.table("task_queue").insert(
            {
                "task_id": task["id"],
                "user_id": user_id,
                "status": "waiting",
            }
        ).execute()
    except APIError as error:
        logger.exception("task_queue insert failed for task_id=%s", task.get("id"))
        raise RuntimeError(f"Queue unavailable: task_queue insert failed: {error}") from error
    if queue_insert.data:
        queue = queue_insert.data[0]
        task.update(
            {
                "queue_id": queue.get("id"),
                "queue_status": queue.get("status"),
                "queue_attempts": queue.get("attempts") or 0,
                "queue_error_message": queue.get("error_message") or "",
                "queue_updated_at": queue.get("updated_at"),
            }
        )
    if used_fallback:
        task.update(
            {
                "product_highlights": product_highlights,
                "target_audience": target_audience,
                "video_style": video_style,
                "use_digital_human": use_digital_human,
                "production_mode": "semi_auto",
                "personal_image_url": personal_image_url,
                "voice_clone_id": voice_clone_id,
                "use_cloned_voice": use_cloned_voice,
                "selling_points": ai_package["selling_points"],
                "hook": ai_package["hook"],
                "shot_list": ai_package["shot_list"],
                "title_options": ai_package["title_options"],
                "caption": ai_package["caption"],
                "cover_text": ai_package["cover_text"],
                "cover_prompt": ai_package["cover_prompt"],
                "hashtags": ai_package["hashtags"],
                "comment_prompt": ai_package["comment_prompt"],
                "closing_cta": ai_package["closing_cta"],
                "admin_workflow": ai_package["admin_workflow"],
            }
        )
    return with_commerce_ai_fallback(task)


def _insert_task_payload(supabase: Client, payload: dict[str, Any]):
    try:
        return supabase.table(TABLE).insert(payload).execute()
    except APIError as error:
        if _is_legacy_status_constraint_error(error) and payload.get("status") == TaskStatus.waiting.value:
            logger.warning("video_tasks status constraint does not allow waiting; retrying insert with pending")
            compatible_payload = dict(payload)
            compatible_payload["status"] = TaskStatus.pending.value
            return supabase.table(TABLE).insert(compatible_payload).execute()
        raise


def _is_legacy_status_constraint_error(error: APIError) -> bool:
    message = str(error)
    return "video_tasks_status_check" in message or "violates check constraint" in message and "status" in message


def _is_missing_generation_error_column(error: APIError) -> bool:
    message = str(error)
    return "generation_error" in message and ("PGRST204" in message or "schema cache" in message)


def _update_video_task(supabase: Client, task_id: str, payload: dict[str, Any]):
    try:
        return supabase.table(TABLE).update(payload).eq("id", task_id).execute()
    except APIError as error:
        if "generation_error" not in payload or not _is_missing_generation_error_column(error):
            raise
        compatible_payload = dict(payload)
        compatible_payload.pop("generation_error", None)
        return supabase.table(TABLE).update(compatible_payload).eq("id", task_id).execute()


def with_commerce_ai_fallback(task: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(task)
    has_ai_package = bool(
        normalized.get("selling_points")
        and normalized.get("hook")
        and normalized.get("shot_list")
        and normalized.get("title_options")
        and normalized.get("admin_workflow")
    )
    if has_ai_package:
        normalized.setdefault("generation_error", "")
        normalized["output_video_url"] = normalized.get("result_video_url")
        normalized.setdefault("voice_duration", None)
        normalized.setdefault("talking_video_url", None)
        normalized.setdefault("queue_id", None)
        normalized.setdefault("queue_status", None)
        normalized.setdefault("queue_attempts", 0)
        normalized.setdefault("queue_error_message", "")
        normalized.setdefault("queue_updated_at", None)
        return normalized

    product_highlights = normalized.get("product_highlights") or normalized.get("script") or ""
    target_audience = normalized.get("target_audience") or "目标用户"
    video_style = normalized.get("video_style") or "hard_sell"
    use_digital_human = normalized.get("use_digital_human")
    if use_digital_human is None:
        use_digital_human = True

    package = generate_commerce_package(
        product_name=normalized.get("product_name") or "商品",
        product_highlights=product_highlights,
        target_audience=target_audience,
        video_style=video_style,
        use_digital_human=bool(use_digital_human),
    )
    normalized.setdefault("product_highlights", product_highlights)
    normalized.setdefault("target_audience", target_audience)
    normalized.setdefault("video_style", video_style)
    normalized.setdefault("use_digital_human", bool(use_digital_human))
    normalized.setdefault("production_mode", "semi_auto")
    normalized["selling_points"] = normalized.get("selling_points") or package["selling_points"]
    normalized["hook"] = normalized.get("hook") or package["hook"]
    normalized["shot_list"] = normalized.get("shot_list") or package["shot_list"]
    normalized["title_options"] = normalized.get("title_options") or package["title_options"]
    normalized["caption"] = normalized.get("caption") or package["caption"]
    normalized["cover_text"] = normalized.get("cover_text") or package["cover_text"]
    normalized["cover_prompt"] = normalized.get("cover_prompt") or package["cover_prompt"]
    normalized["hashtags"] = normalized.get("hashtags") or package["hashtags"]
    normalized["comment_prompt"] = normalized.get("comment_prompt") or package["comment_prompt"]
    normalized["closing_cta"] = normalized.get("closing_cta") or package["closing_cta"]
    normalized["admin_workflow"] = normalized.get("admin_workflow") or package["admin_workflow"]
    normalized.setdefault("generation_error", "")
    normalized["output_video_url"] = normalized.get("result_video_url")
    normalized.setdefault("voice_duration", None)
    normalized.setdefault("talking_video_url", None)
    normalized.setdefault("queue_id", None)
    normalized.setdefault("queue_status", None)
    normalized.setdefault("queue_attempts", 0)
    normalized.setdefault("queue_error_message", "")
    normalized.setdefault("queue_updated_at", None)
    return normalized


def with_queue_state(supabase: Client, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not tasks:
        return tasks
    task_ids = [task["id"] for task in tasks if task.get("id")]
    try:
        queue_result = (
            supabase.table("task_queue")
            .select("id, task_id, status, attempts, error_message, updated_at")
            .in_("task_id", task_ids)
            .order("updated_at", desc=True)
            .execute()
        )
    except Exception:
        logger.exception("Failed to read task_queue state")
        return tasks

    queue_by_task_id: dict[str, dict[str, Any]] = {}
    for item in queue_result.data:
        queue_by_task_id.setdefault(item["task_id"], item)

    enriched = []
    for task in tasks:
        normalized = dict(task)
        queue = queue_by_task_id.get(task.get("id"))
        if queue:
            normalized.update(
                {
                    "queue_id": queue.get("id"),
                    "queue_status": queue.get("status"),
                    "queue_attempts": queue.get("attempts") or 0,
                    "queue_error_message": queue.get("error_message") or "",
                    "queue_updated_at": queue.get("updated_at"),
                }
            )
        enriched.append(normalized)
    return enriched


def list_user_tasks(supabase: Client, user_id: str) -> list[dict[str, Any]]:
    result = (
        supabase.table(TABLE)
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [with_commerce_ai_fallback(task) for task in result.data]


def get_task(supabase: Client, task_id: str) -> dict[str, Any] | None:
    result = supabase.table(TABLE).select("*").eq("id", task_id).limit(1).execute()
    if not result.data:
        return None
    return with_queue_state(supabase, [with_commerce_ai_fallback(result.data[0])])[0]


def get_user_task(supabase: Client, task_id: str, user_id: str) -> dict[str, Any] | None:
    result = (
        supabase.table(TABLE)
        .select("*")
        .eq("id", task_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return with_commerce_ai_fallback(result.data[0]) if result.data else None


def list_all_tasks(supabase: Client) -> list[dict[str, Any]]:
    result = supabase.table(TABLE).select("*").order("created_at", desc=True).execute()
    return with_queue_state(supabase, [with_commerce_ai_fallback(task) for task in result.data])


def update_task(
    supabase: Client,
    task_id: str,
    *,
    status: TaskStatus | None = None,
    result_video_url: str | None = None,
    subtitle_url: str | None = None,
    subtitle_status: str | None = None,
    cloned_voice_url: str | None = None,
    cosyvoice_status: str | None = None,
    heygen_avatar_id: str | None = None,
    heygen_voice_id: str | None = None,
    heygen_video_id: str | None = None,
    heygen_video_url: str | None = None,
    admin_notes: str | None = None,
    generation_error: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if status:
        payload["status"] = status.value
    if result_video_url:
        payload["result_video_url"] = result_video_url
    if subtitle_url:
        payload["subtitle_url"] = subtitle_url
    if subtitle_status:
        payload["subtitle_status"] = subtitle_status
    if cloned_voice_url:
        payload["cloned_voice_url"] = cloned_voice_url
    if cosyvoice_status:
        payload["cosyvoice_status"] = cosyvoice_status
    if heygen_avatar_id is not None:
        payload["heygen_avatar_id"] = heygen_avatar_id
    if heygen_voice_id is not None:
        payload["heygen_voice_id"] = heygen_voice_id
    if heygen_video_id is not None:
        payload["heygen_video_id"] = heygen_video_id
    if heygen_video_url is not None:
        payload["heygen_video_url"] = heygen_video_url
    if admin_notes is not None:
        payload["admin_notes"] = admin_notes
    if generation_error is not None:
        payload["generation_error"] = generation_error

    result = _update_video_task(supabase, task_id, payload)
    if status:
        queue_status = {
            TaskStatus.waiting: "waiting",
            TaskStatus.processing: "processing",
            TaskStatus.completed: "completed",
            TaskStatus.failed: "failed",
        }.get(status)
        if queue_status:
            queue_payload: dict[str, Any] = {"status": queue_status}
            if generation_error is not None:
                queue_payload["error_message"] = generation_error
            elif queue_status in {"waiting", "processing", "completed"}:
                queue_payload["error_message"] = ""
            try:
                supabase.table("task_queue").update(queue_payload).eq("task_id", task_id).execute()
            except Exception:
                logger.exception("Failed to sync task_queue status for task_id=%s", task_id)
    return with_queue_state(supabase, [with_commerce_ai_fallback(result.data[0])])[0]


def delete_user_task(supabase: Client, task_id: str, user_id: str) -> None:
    supabase.table(TABLE).delete().eq("id", task_id).eq("user_id", user_id).execute()


def requeue_user_task(supabase: Client, task_id: str, user_id: str) -> dict[str, Any]:
    task = get_user_task(supabase, task_id, user_id)
    if not task:
        raise ValueError("Task not found")
    _update_video_task(supabase, task_id, {"status": "waiting", "generation_error": ""})
    try:
        existing = supabase.table("task_queue").select("id").eq("task_id", task_id).limit(1).execute()
        if existing.data:
            supabase.table("task_queue").update({"status": "waiting", "attempts": 0, "error_message": ""}).eq("task_id", task_id).execute()
        else:
            supabase.table("task_queue").insert({"task_id": task_id, "user_id": user_id, "status": "waiting"}).execute()
    except APIError as error:
        logger.exception("task_queue requeue failed for task_id=%s", task_id)
        raise RuntimeError(f"Queue unavailable: task_queue requeue failed: {error}") from error
    return get_user_task(supabase, task_id, user_id) or task
