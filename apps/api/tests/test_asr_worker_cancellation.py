import asyncio
import queue

from app.services import asr_service


class _Commands:
    def put(self, _item):
        return None


class _Results:
    def get(self, _block, _timeout):
        raise queue.Empty


class _Process:
    pid = 4242

    def __init__(self):
        self.alive = True
        self.terminate_called = False
        self.kill_called = False

    def is_alive(self):
        return self.alive

    def terminate(self):
        self.terminate_called = True
        self.alive = False

    def kill(self):
        self.kill_called = True
        self.alive = False

    def join(self, timeout):
        assert timeout in {2, 3}


def test_cancelled_asr_wait_terminates_worker_before_returning(tmp_path, monkeypatch):
    manager = asr_service._ASRProcessManager()
    process = _Process()
    commands = _Commands()
    results = _Results()
    manager._process = process
    manager._commands = commands
    manager._results = results
    monkeypatch.setattr(manager, "_ensure_worker", lambda: (commands, results, process.pid))

    async def exercise():
        task = asyncio.create_task(manager.transcribe(tmp_path / "audio.wav", "zh", 170.3))
        await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(exercise())

    assert process.terminate_called is True
    assert process.is_alive() is False
    assert manager.status()["task_active"] is False
    assert manager.status()["residual_worker"] is False


def test_residual_asr_worker_rejects_new_task_without_queueing(tmp_path):
    manager = asr_service._ASRProcessManager()
    manager._residual_worker = True

    result = asyncio.run(manager.transcribe(tmp_path / "audio.wav", "zh", 170.3))

    assert result.ok is False
    assert result.error_code == "asr_worker_residual"
    assert result.retryable is True
