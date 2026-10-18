"""Índice de busca: SQLite FTS5, derivado dos arquivos e reconstruído quando os
HEADs de main/inbox mudam. É cache — pode ser apagado a qualquer momento."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from .schema import Memory

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS mem USING fts5(
    id UNINDEXED, title, body, tags,
    type UNINDEXED, scope UNINDEXED, project UNINDEXED,
    status UNINDEXED, origin UNINDEXED, pinned UNINDEXED, data UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


class Index:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.executescript(_SCHEMA)

    def signature(self) -> str | None:
        row = self.db.execute("SELECT v FROM meta WHERE k='sig'").fetchone()
        return row[0] if row else None

    def rebuild(self, memories: list[Memory], sig: str) -> None:
        with self.db:
            self.db.execute("DELETE FROM mem")
            self.db.executemany(
                "INSERT INTO mem VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [
                    (
                        m.id, m.title, m.body, " ".join(m.tags), m.type, m.scope,
                        m.project or "", m.status, m.origin, int(m.pinned),
                        json.dumps(m.to_dict(), ensure_ascii=False),
                    )
                    for m in memories
                ],
            )
            self.db.execute("INSERT OR REPLACE INTO meta VALUES ('sig', ?)", (sig,))

    def ensure(self, memories_fn, sig: str) -> None:
        if self.signature() != sig:
            self.rebuild(memories_fn(), sig)

    @staticmethod
    def _fts_query(q: str) -> str:
        words = re.findall(r"\w+", q, flags=re.UNICODE)
        return " OR ".join(f'"{w}"' for w in words if len(w) > 1)

    def search(
        self,
        query: str,
        *,
        project: str | None = None,
        scope: str | None = None,
        type: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        fts = self._fts_query(query)
        if not fts:
            return []
        rows = self.db.execute(
            "SELECT data, bm25(mem, 0, 5.0, 1.0, 2.0) AS score, origin, status, project, scope "
            "FROM mem WHERE mem MATCH ?",
            (fts,),
        ).fetchall()
        results = []
        for data, score, origin, status, proj, sc in rows:
            if scope and sc != scope:
                continue
            if type and json.loads(data)["type"] != type:
                continue
            # escopo project só aparece para o próprio projeto (ou sem filtro de projeto)
            if sc == "project" and project and proj != project:
                continue
            rank = -score  # bm25: menor é melhor
            if origin == "inbox":
                rank *= 0.6
            elif status == "provisional":
                rank *= 0.8
            if project and proj == project:
                rank *= 1.3
            results.append((rank, data))
        results.sort(key=lambda r: -r[0])
        out = []
        for rank, data in results[:limit]:
            d = json.loads(data)
            body = d.pop("body", "")
            d["trecho"] = body[:280] + ("…" if len(body) > 280 else "")
            d["relevancia"] = round(rank, 3)
            out.append(d)
        return out
