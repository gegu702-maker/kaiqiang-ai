# Kaiqiang MuseTalk GPU Service

Run this on the AutoDL MuseTalk machine:

```bash
cd /root/MuseTalk
/root/miniconda3/envs/musetalk/bin/pip install fastapi "uvicorn[standard]" httpx pyyaml python-multipart
cp /root/autodl-tmp/kaiqiang-service/musetalk_service.py /root/MuseTalk/kaiqiang_musetalk_service.py
cp /root/autodl-tmp/kaiqiang-service/start_musetalk.sh /root/autodl-tmp/start_musetalk.sh
cp /root/autodl-tmp/kaiqiang-service/idle_shutdown.sh /root/autodl-tmp/idle_shutdown.sh
chmod +x /root/autodl-tmp/start_musetalk.sh /root/autodl-tmp/idle_shutdown.sh
/root/autodl-tmp/start_musetalk.sh
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
