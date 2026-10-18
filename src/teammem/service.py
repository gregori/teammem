"""Operações de alto nível usadas pelo MCP e pela CLI (o contrato da docs/SPEC.md)."""

from __future__ import annotations

from . import curator, safety
from .config import Config
from .index import Index
from .schema import Memory, new_memory
from .store import GitError, Store


class Service:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.store = Store(cfg)
        self._index: Index | None = None

    # ------------------------------------------------------------ infra
    def refresh(self, force: bool = False) -> dict:
        try:
            return self.store.sync(force=force)
        except GitError as e:
            # sem rede ou sem acesso: segue com o que existe localmente
            return {"synced": False, "errors": [str(e)]}

    @property
    def index(self) -> Index:
        if self._index is None:
            self._index = Index(self.cfg.index_path)
        sig = f"{self.store.head('main')}:{self.store.head('inbox')}"
        self._index.ensure(self.store.all_memories, sig)
        return self._index

    def _visible(self, m: Memory, project: str | None) -> bool:
        return not (m.scope == "project" and project and m.project != project)

    # ------------------------------------------------------------ leitura
    def list_index(self, scope: str | None = None, project: str | None = None,
                   include_inbox: bool = True) -> list[dict]:
        self.refresh()
        project = project or self.cfg.project
        mems = self.store.all_memories() if include_inbox else self.store.main_memories()
        return [
            m.summary()
            for m in mems
            if self._visible(m, project) and (not scope or m.scope == scope)
        ]

    def read(self, ids: list[str]) -> list[dict]:
        self.refresh()
        by_id = {m.id: m for m in self.store.all_memories()}
        return [by_id[i].to_dict() if i in by_id else {"id": i, "erro": "não encontrada"}
                for i in ids]

    def search(self, query: str, scope: str | None = None, type: str | None = None,
               project: str | None = None, limit: int = 10) -> list[dict]:
        self.refresh()
        return self.index.search(query, project=project or self.cfg.project, scope=scope,
                                 type=type, limit=limit)

    def pinned(self, project: str | None = None) -> list[Memory]:
        self.refresh()
        project = project or self.cfg.project
        return [m for m in self.store.main_memories() if m.pinned and self._visible(m, project)]

    # ------------------------------------------------------------ escrita
    def propose(self, *, title: str, body: str, type: str, scope: str = "project",
                project: str | None = None, source: str | None = None,
                confidence: str = "medium", tags: list[str] | None = None,
                pinned: bool = False) -> dict:
        scan = safety.scan(f"{title}\n{body}")
        if not scan.ok:
            return {"status": "recusada", "motivos": scan.blocked}
        if scope == "project":
            project = project or self.cfg.project
        mem = new_memory(
            title=title, body=body, type=type, scope=scope, project=project,
            author=self.cfg.author, source=source, confidence=confidence, tags=tags,
            pinned=pinned,
        )
        self.refresh()
        dup = curator.classify(mem, self.store.all_memories(), self.store.policy())
        res = self.store.propose(mem)
        if dup.similar:
            res["similares"] = [{"id": i, "similaridade": round(s, 2)} for i, s in dup.similar]
        if scan.review:
            res["alertas"] = scan.review
        return res
