# Kaiqiang MuseTalk GPU Service

Run this on the AutoDL MuseTalk machine:

```bash
cd /root/MuseTalk
/root/miniconda3/envs/musetalk/bin/pip install fastapi "uvicorn[standard]" httpx pyyaml python-multipart
cp /root/autodl-tmp/kaiqiang-service/musetalk_service.py /root/MuseTalk/kaiqiang_musetalk_service.py
MUSETALK_API_KEY="change-me" nohup /root/miniconda3/envs/musetalk/bin/uvicorn kaiqiang_musetalk_service:app --host 0.0.0.0 --port 6006 > /root/MuseTalk/kaiqiang_musetalk_service.log 2>&1 &
curl http://127.0.0.1:6006/health
```

API:

```http
POST /generate
Content-Type: application/json
Authorization: Bearer <MUSETALK_API_KEY>
```

```json
{
  "video_url": "https://...",
  "audio_url": "https://...",
  "task_id": "avatar-task-id"
}
```

Response:

```json
{
  "status": "completed",
  "video_url": "https://.../results/avatar-task-id.mp4"
}
```
