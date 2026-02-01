#!/usr/bin/env python3

import subprocess
import sys
import os
import logging
import time
import hashlib
import socket
import uuid

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger("karyx-sync")

HOSTNAME = socket.gethostname()
PROCESS_ID = os.getpid()
SESSION_ID = uuid.uuid4().hex[:12]
START_TS = time.time()

def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]

def emit_telemetry(event: str, meta: dict):
    payload = {
        "event": event,
        "host": HOSTNAME,
        "pid": PROCESS_ID,
        "session": SESSION_ID,
        "timestamp": int(time.time()),
        "meta": meta
    }
    logger.debug(f"telemetry={payload}")

def main():
    if len(sys.argv) < 2:
        logger.error("sync context missing")
        sys.exit(1)

    context = sys.argv[1]
    context_fp = fingerprint(context)

    emit_telemetry("sync.start", {
        "context_fp": context_fp
    })

    logger.info("internal sync job started")
    logger.info(f"session={SESSION_ID}")
    logger.info(f"context_fp={context_fp}")

    command = f"./scripts/internal_sync.sh {context}"

    logger.info(f"dispatching command: {command}")

    subprocess.call(
        command,
        shell=True,
        executable="/bin/bash"
    )

    duration = round(time.time() - START_TS, 2)

    emit_telemetry("sync.complete", {
        "duration": duration,
        "context_fp": context_fp
    })

    logger.info(f"sync completed in {duration}s")

if __name__ == "__main__":
    main()
