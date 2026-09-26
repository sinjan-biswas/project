"""
Read-only screening history, queried directly from the Hyperledger Fabric ledger.

Avoids touching blockchain/client.py by shelling out to `peer chaincode query`.
Uses function names already defined in screening-chaincode-go/screening.go:
    - QueryScreeningsByCheckpoint(checkpoint_id)
    - GetScreening(screening_id)
    - GetScreeningPII(screening_id)
"""
import json
import os
import subprocess

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v2/history", tags=["history"])

CHANNEL = "screening-channel"
CHAINCODE = "screening"


def _peer_query(function: str, *args):
    """Run a peer chaincode query and return parsed JSON (or raw text)."""
    payload = {"Args": [function] + [str(a) for a in args]}
    cmd = [
        "peer", "chaincode", "query",
        "-C", CHANNEL,
        "-n", CHAINCODE,
        "-c", json.dumps(payload),
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    out = result.stdout.strip()
    if not out:
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"raw": out}


@router.get("")
async def screening_history(
    checkpoint: str = Query("JFK_01", description="Checkpoint ID to filter by"),
    limit: int = Query(50, ge=1, le=500),
):
    """
    Return screenings recorded at a given checkpoint, most recent first.
    """
    try:
        rows = _peer_query("QueryScreeningsByCheckpoint", checkpoint)
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"Ledger query failed: {(e.stderr or str(e)).strip()}")
    except FileNotFoundError:
        raise HTTPException(503, "peer binary not on PATH — start uvicorn from a shell with fabric-samples/bin on PATH")

    if not isinstance(rows, list):
        rows = []

    rows.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return {"checkpoint_id": checkpoint, "count": len(rows), "screenings": rows[:limit]}


@router.get("/{screening_id}")
async def screening_detail(screening_id: str):
    """
    Return a single screening record. Attempts to include the private PII
    collection entry, but that may be unavailable after block-to-live expires.
    """
    try:
        record = _peer_query("GetScreening", screening_id)
    except subprocess.CalledProcessError as e:
        raise HTTPException(404, f"Screening not found: {(e.stderr or str(e)).strip()}")
    except FileNotFoundError:
        raise HTTPException(503, "peer binary not on PATH")

    pii = None
    try:
        pii = _peer_query("GetScreeningPII", screening_id)
    except subprocess.CalledProcessError:
        pass  # PII may have expired or not exist

    return {"screening": record, "pii": pii}