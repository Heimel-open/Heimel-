"""Public HEIMEL cumulative-exposure *reference* (not production authority).

No dependency on private runtime or Enterprise policy. The caller must have
already established current authority and trusted scope/limits. This ledger
does not issue permits or execute effects.

Amounts are nonnegative *integer* minor units (e.g. øre), not binary floats.
SQLite uses BEGIN IMMEDIATE to serialize writers, including across processes.
Unknown outcomes are retained even after the configured rolling window.
"""
from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from pathlib import Path


class ExposureDenied(ValueError):
    """Fail-closed: reservation or reconciliation is not admissible."""


@dataclass(frozen=True)
class Request:
    tenant: str
    scope: str
    dimension: str
    unit: str
    request_id: str
    amount: int
    ceiling: int
    now: int
    window: int

    def validate(self) -> None:
        strings = (self.tenant, self.scope, self.dimension, self.unit, self.request_id)
        if any(not isinstance(v, str) or not v.strip() for v in strings):
            raise ExposureDenied("invalid scope or identity")
        numeric = (self.amount, self.ceiling, self.now, self.window)
        if any(type(v) is not int for v in numeric):
            raise ExposureDenied("integer amounts and time required")
        if self.amount < 0 or self.ceiling < 0 or self.now < 0 or self.window <= 0:
            raise ExposureDenied("invalid budget or time window")


class Ledger:
    """Reference-only SQLite accounting; intentionally no authority handling."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        with self._db() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS reservations (
                   tenant TEXT NOT NULL, request_id TEXT NOT NULL,
                   scope TEXT NOT NULL, dimension TEXT NOT NULL, unit TEXT NOT NULL,
                   amount INTEGER NOT NULL, created INTEGER NOT NULL,
                   state TEXT NOT NULL CHECK(state IN ('reserved','unknown','released')),
                   PRIMARY KEY(tenant,request_id))"""
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS exposure_scope ON reservations(tenant,scope,dimension,unit,state,created)"
            )

    def _db(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        return db

    def reserve(self, request: Request) -> str:
        request.validate()
        try:
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                existing = db.execute(
                    "SELECT * FROM reservations WHERE tenant=? AND request_id=?",
                    (request.tenant, request.request_id),
                ).fetchone()
                if existing:
                    fields = ("tenant", "scope", "dimension", "unit", "request_id", "amount")
                    if any(existing[k] != getattr(request, k) for k in fields):
                        raise ExposureDenied("idempotency key collision")
                    if existing["state"] == "released":
                        raise ExposureDenied("released request cannot be replayed")
                    return existing["state"]  # evidence only, never a new permit
                used = db.execute(
                    """SELECT COALESCE(SUM(amount),0) FROM reservations
                       WHERE tenant=? AND scope=? AND dimension=? AND unit=?
                       AND (state='unknown' OR
                            (state='reserved' AND created>=?))""",
                    (request.tenant, request.scope, request.dimension,
                     request.unit, request.now - request.window),
                ).fetchone()[0]
                if used > request.ceiling or request.amount > request.ceiling - used:
                    raise ExposureDenied("cumulative ceiling exceeded")
                db.execute(
                    """INSERT INTO reservations
                       (tenant,request_id,scope,dimension,unit,amount,created,state)
                       VALUES (?,?,?,?,?,?,?,'reserved')""",
                    (request.tenant, request.request_id, request.scope,
                     request.dimension, request.unit, request.amount, request.now),
                )
                return "reserved"
        except sqlite3.Error as exc:
            raise ExposureDenied("ledger unavailable") from exc

    def transition(self, tenant: str, request_id: str, state: str) -> None:
        if (not isinstance(tenant, str) or not tenant or
            not isinstance(request_id, str) or not request_id or
            state not in ("unknown", "released")):
            raise ExposureDenied("invalid transition")
        try:
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                old = db.execute(
                    "SELECT state FROM reservations WHERE tenant=? AND request_id=?",
                    (tenant, request_id),
                ).fetchone()
                if not old:
                    raise ExposureDenied("reservation missing")
                if old["state"] == state:
                    return
                if old["state"] != "reserved":
                    raise ExposureDenied("only pending reservation may transition")
                db.execute(
                    "UPDATE reservations SET state=? WHERE tenant=? AND request_id=?",
                    (state, tenant, request_id),
                )
        except sqlite3.Error as exc:
            raise ExposureDenied("ledger unavailable") from exc

    def state(self, tenant: str, request_id: str) -> str | None:
        try:
            with self._db() as db:
                row = db.execute(
                    "SELECT state FROM reservations WHERE tenant=? AND request_id=?",
                    (tenant, request_id),
                ).fetchone()
                return row["state"] if row else None
        except sqlite3.Error as exc:
            raise ExposureDenied("ledger unavailable") from exc
