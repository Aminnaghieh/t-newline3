"""Sample production-ready FastAPI app for testing Liara SRE Agent."""

import os
import sys
from fastapi import FastAPI, HTTPException, Response

app = FastAPI(
    title="Liara Demo Microservice",
    description="سرویس نمونه جهت تست و نمایش قابلیت‌های SRE Agent در چالش لیارا",
    version="1.0.0",
)

# Simulated in-memory leak storage
_leak_buffer: list[bytes] = []


@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Liara Demo App",
        "message": "خوش آمدید! سرویس با موفقیت روی لیارا در حال اجراست 🚀",
        "env": os.environ.get("ENVIRONMENT", "production"),
        "hostname": os.uname().nodename if hasattr(os, "uname") else "local",
    }


@app.get("/health")
def health_check():
    """Liveness & readiness probe endpoint."""
    return {"status": "healthy", "uptime_ok": True}


@app.get("/simulate-oom")
def simulate_oom(mb: int = 150):
    """Simulate memory allocation spike to trigger SRE Agent Alert / RCA."""
    global _leak_buffer
    try:
        # Allocate bytes in memory
        _leak_buffer.append(b"X" * (mb * 1024 * 1024))
        allocated = len(_leak_buffer) * mb
        return {
            "status": "memory_allocated",
            "allocated_mb": allocated,
            "warning": "مصرف حافظه بالا رفت — آماده تست liara-agent debug",
        }
    except MemoryError:
        raise HTTPException(status_code=500, detail="Out of Memory (OOM) simulated!")


@app.get("/simulate-error")
def simulate_error():
    """Simulate an unhandled 500 error for troubleshooting demonstration."""
    raise HTTPException(status_code=500, detail="خطای داخلی سرور (Database Connection Refused)")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
