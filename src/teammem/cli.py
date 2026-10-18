"""CLI: `teammem <comando>`. Todos os comandos aceitam --repo/--name/--home."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path

from . import __version__, agentsmd, config, curator, install, review


def _out(data) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _cfg(a: argparse.Namespace) -> config.Config:
    return config.load(repo=a.repo, name=a.name, home=a.home, author=a.author, project=a.project)


def _svc(a):
    from .service import Service

    return Service(_cfg(a))


# ---------------------------------------------------------------- comandos
def cmd_serve(a):
    from .server import run

    run(_cfg(a))


def cmd_sync(a):
    _out(_svc(a).refresh(force=True))


def cmd_list(a):
    _out(_svc(a).list_index(scope=a.scope, include_inbox=not a.main_only))


def cmd_show(a):
    _out(_svc(a).read(a.ids))


def cmd_search(a):
    _out(_svc(a).search(" ".join(a.query), scope=a.scope, type=a.type, limit=a.limit))


def cmd_propose(a):
    body = a.body if a.body is not None else sys.stdin.read()
    _out(_svc(a).propose(title=a.title, body=body, type=a.type, scope=a.scope,
                         project=a.for_project, source=a.source, confidence=a.confidence,
                         tags=a.tag, pinned=a.pinned))


def cmd_review(a):
    svc = _svc(a)
    svc.refresh(force=True)
    if a.auto:
        _out(review.auto(svc.store))
        return
    verdicts = review.pending(svc.store)
    if not verdicts:
        print("Inbox vazia: nada a revisar.")
        return
    if a.list:
        _out([v.to_dict() for v in verdicts])
        return
    if a.approve:
        ids = [i.strip() for i in a.approve.split(",") if i.strip()]
    else:
        ids = []
        for v in verdicts:
            m = v.memory
            print(f"\n[{v.tier.upper()}] {m.id}\n  {m.title}  ({m.type}, {m.scope}"
                  f"{'/' + m.project if m.project else ''}, por {m.author})")
            print("  " + "\n  ".join(m.body.splitlines()))
            for r in v.reasons:
                print(f"  ! {r}")
            if v.tier == "bloqueado":
                print("  -> bloqueada: não pode ser promovida")
                continue
            if input("  Aprovar? [s/N] ").strip().lower() in ("s", "sim", "y", "yes"):
                ids.append(m.id)
    if not ids:
        print("Nada aprovado.")
        return
    _out(review.promote(svc.store, ids, mode=a.mode))


def cmd_gc(a):
    _out(review.gc(_svc(a).store))


def cmd_stale(a):
    svc = _svc(a)
    svc.refresh()
    _out([m.summary() | {"review_by": m.review_by}
          for m in svc.store.main_memories() if curator.stale(m)])


def cmd_agents_md(a):
    svc = _svc(a)
    svc.refresh()
    pol = curator.policy_with_defaults(svc.store.policy())
    block = agentsmd.render(svc.pinned(), svc.cfg.name, a.server or f"teammem-{svc.cfg.name}",
                            pol["pinned_max"])
    if a.stdout:
        print(block)
    else:
        changed = agentsmd.write(Path(a.path), block)
        print(f"{a.path}: {'atualizado' if changed else 'inalterado'}")


def cmd_install(a):
    cfg = _cfg(a)
    pdir = Path(a.project_dir).resolve()
    harnesses = install.HARNESSES if a.harness == ["all"] else a.harness
    server = a.server or f"teammem-{cfg.name}"
    res = {"mcp": install.install(list(harnesses), project_dir=pdir, repo=cfg.repo,
                                  name=cfg.name, source=a.source, server=server)}
    if not a.no_skill:
        res["skills"] = install.install_skill(pdir, list(harnesses))
    if not a.no_agents_md:
        from .service import Service

        svc = Service(cfg)
        svc.refresh(force=True)
        pol = curator.policy_with_defaults(svc.store.policy())
        block = agentsmd.render(svc.pinned(), cfg.name, server, pol["pinned_max"])
        res["agents_md"] = agentsmd.write(pdir / "AGENTS.md", block)
        if "claude" in harnesses:
            res["claude_md_import"] = install.ensure_claude_import(pdir)
    _out(res)


def cmd_init(a):
    """Cria a estrutura de um repositório de memórias (acervo) a partir do template."""
    dest = Path(a.dir).resolve()
    if dest.exists() and any(dest.iterdir()):
        sys.exit(f"{dest} não está vazio")
    tpl = resources.files("teammem") / "templates" / "memory-repo"
    with resources.as_file(tpl) as src:
        shutil.copytree(src, dest, dirs_exist_ok=True)
    prof = dest / f".teammem.{a.profile}.yaml"
    (dest / ".teammem.yaml").write_text(prof.read_text(encoding="utf-8"), encoding="utf-8")
    for p in dest.glob(".teammem.*.yaml"):
        p.unlink()
    wf = dest / ".github" / "workflows"
    if a.profile == "work":
        shutil.rmtree(wf, ignore_errors=True)
    else:
        (dest / ".github" / "CODEOWNERS").unlink(missing_ok=True)
    for d in ("global", "team", "org", "project"):
        (dest / d).mkdir(exist_ok=True)
        (dest / d / ".gitkeep").touch()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=dest, check=True)
    print(f"Acervo criado em {dest} (perfil {a.profile}).\n"
          "Próximos passos: git add -A && git commit -m 'acervo inicial' && "
          "git remote add origin <url> && git push -u origin main")


def cmd_doctor(a):
    checks = []

    def ok(name, cond, detail=""):
        checks.append({"check": name, "ok": bool(cond), "detalhe": detail})

    ok("git instalado", shutil.which("git"))
    ok("uvx instalado", shutil.which("uvx"), "necessário para os harnesses iniciarem o MCP")
    try:
        cfg = _cfg(a)
        ok("repo configurado", True, cfg.repo)
        from .service import Service

        svc = Service(cfg)
        r = svc.refresh(force=True)
        ok("sync", not r.get("errors"), "; ".join(r.get("errors", [])))
        ok("memórias legíveis", True, f"{len(svc.store.main_memories())} na main, "
                                       f"{len(svc.store.inbox_memories())} na inbox")
        ok("índice", svc.index is not None, str(cfg.index_path))
        ok("fila offline vazia", svc.store.pending_push() == 0,
           f"{svc.store.pending_push()} commits aguardando push")
        ok("autor definido", cfg.author,
           cfg.author or "defina TEAMMEM_AUTHOR ou git config user.name")
    except SystemExit as e:
        ok("repo configurado", False, str(e))
    for c in checks:
        print(f"{'✔' if c['ok'] else '✘'} {c['check']}" + (f" — {c['detalhe']}" if c['detalhe'] else ""))
    sys.exit(0 if all(c["ok"] for c in checks) else 1)


# ---------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="teammem", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo", help="URL ou caminho do acervo (TEAMMEM_REPO)")
    common.add_argument("--name", help="nome local do acervo (TEAMMEM_NAME)")
    common.add_argument("--home", help="pasta de dados (TEAMMEM_HOME, padrão ~/.teammem)")
    common.add_argument("--author", help="autor das propostas (TEAMMEM_AUTHOR)")
    common.add_argument("--project", help="projeto atual (TEAMMEM_PROJECT, padrão: pasta git)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        sp = sub.add_parser(name, parents=[common], help=help_)
        sp.set_defaults(fn=fn)
        return sp

    add("serve", cmd_serve, "inicia o servidor MCP (stdio)")
    add("sync", cmd_sync, "força pull/push do acervo")
    sp = add("list", cmd_list, "lista o índice")
    sp.add_argument("--scope")
    sp.add_argument("--main-only", action="store_true")
    sp = add("show", cmd_show, "mostra memórias por id")
    sp.add_argument("ids", nargs="+")
    sp = add("search", cmd_search, "busca")
    sp.add_argument("query", nargs="+")
    sp.add_argument("--scope")
    sp.add_argument("--type")
    sp.add_argument("--limit", type=int, default=10)
    sp = add("propose", cmd_propose, "propõe memória (corpo via --body ou stdin)")
    sp.add_argument("--title", required=True)
    sp.add_argument("--body")
    sp.add_argument("--type", required=True, choices=["decision", "gotcha", "convention",
                                                       "pattern", "anti-pattern"])
    sp.add_argument("--scope", default="project", choices=["global", "team", "org", "project"])
    sp.add_argument("--for-project", help="projeto da memória (padrão: --project)")
    sp.add_argument("--source")
    sp.add_argument("--confidence", default="medium", choices=["low", "medium", "high"])
    sp.add_argument("--tag", action="append")
    sp.add_argument("--pinned", action="store_true")
    sp = add("review", cmd_review, "revisa a inbox e promove para a main")
    sp.add_argument("--auto", action="store_true", help="modo CI particular: auto->main, humano->PR")
    sp.add_argument("--list", action="store_true", help="só lista com a classificação")
    sp.add_argument("--approve", help="ids separados por vírgula (não interativo)")
    sp.add_argument("--mode", default="pr", choices=["pr", "direct"])
    add("gc", cmd_gc, "limpa a inbox (promovidas e expiradas)")
    add("stale", cmd_stale, "lista memórias com review_by vencido")
    sp = add("agents-md", cmd_agents_md, "gera/atualiza o bloco do AGENTS.md")
    sp.add_argument("--path", default="AGENTS.md")
    sp.add_argument("--server")
    sp.add_argument("--stdout", action="store_true")
    sp = add("install", cmd_install, "configura MCP, skill e AGENTS.md nos harnesses")
    sp.add_argument("--harness", nargs="+", default=["all"],
                    help=f"{', '.join(install.HARNESSES)} ou all")
    sp.add_argument("--project-dir", default=".")
    sp.add_argument("--source", default="teammem",
                    help="origem do pacote p/ uvx: 'teammem', 'git+https://…', wheel local")
    sp.add_argument("--server", help="nome do servidor MCP (padrão teammem-<nome>)")
    sp.add_argument("--no-skill", action="store_true")
    sp.add_argument("--no-agents-md", action="store_true")
    sp = sub.add_parser("init", help="cria um acervo novo a partir do template")
    sp.add_argument("dir")
    sp.add_argument("--profile", default="personal", choices=["personal", "work"])
    sp.set_defaults(fn=cmd_init)
    add("doctor", cmd_doctor, "diagnóstico da instalação")
    return p


def main(argv: list[str] | None = None) -> None:
    a = build_parser().parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
