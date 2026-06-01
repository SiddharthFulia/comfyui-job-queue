"""Register a custom handler for a new job kind."""

from __future__ import annotations

from comfy_queue.job import Job
from comfy_queue.registry import dispatch, register


@register("lipsync")
def handle_lipsync(job: Job, ctx):
    audio = job.payload.get("audio")
    video = job.payload.get("video")
    if not audio or not video:
        raise ValueError("lipsync job needs payload.audio and payload.video")

    if "on_progress" in ctx:
        ctx["on_progress"](0.1, "loading audio")
        ctx["on_progress"](0.5, "aligning")
        ctx["on_progress"](0.9, "rendering")
    return {"output": f"lipsync_{job.id}.mp4"}


if __name__ == "__main__":
    j = Job(
        id="demo-lipsync-1",
        kind="lipsync",
        lane="lipsync",
        payload={"audio": "a.wav", "video": "v.mp4"},
    )
    result = dispatch(j, {"on_progress": lambda p, m: print(f"  {p:.0%} {m}")})
    print("result:", result)
