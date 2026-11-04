"""Command line: iqbank collect | extract | dedupe | report | run | status."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import click

from iqbank import __version__
from iqbank.config import Settings
from iqbank.llm import ClaudeJSON, FatalLLMError

log = logging.getLogger("iqbank")


@dataclass
class App:
    settings: Settings
    dry_run: bool

    def store(self, dry_run: bool):
        from iqbank.store import Store

        return Store(self.settings.db_path, readonly=dry_run)

    def llm(self) -> ClaudeJSON:
        s = self.settings
        return ClaudeJSON(s.model, s.effort, use_fallbacks=s.use_fallbacks)


def setup_logging(verbose: int, log_file: Path | None) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
        force=True,
    )
    noisy_level = logging.DEBUG if verbose >= 2 else logging.WARNING
    for name in ("httpx", "httpcore", "httpx2", "anthropic", "prawcore", "praw", "urllib3", "trafilatura", "htmldate"):
        logging.getLogger(name).setLevel(noisy_level)


def dry_run_option(func):
    return click.option(
        "--dry-run",
        "local_dry_run",
        is_flag=True,
        help="Show what would happen. No network calls, no Claude calls, nothing written.",
    )(func)


def _is_dry(app: App, local: bool) -> bool:
    return app.dry_run or local


def _fatal(exc: Exception) -> None:
    raise click.ClickException(str(exc))


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="iqbank")
@click.option("--company", help="Target company (default: Glean).")
@click.option("--role", "roles", multiple=True, help="Target role; repeat for several (default: Platform Security Engineer, Software Engineer).")
@click.option("--config", "config_path", type=click.Path(path_type=Path, exists=True, dir_okay=False),
              help="TOML settings file (default: ./iqbank.toml if present).")
@click.option("--env-file", type=click.Path(path_type=Path, exists=True, dir_okay=False),
              help="Credentials file (default: ./.env).")
@click.option("--db", "db_path", type=click.Path(path_type=Path, dir_okay=False), help="SQLite path (default: ./iqbank.db).")
@click.option("--inbox", "inbox_dir", type=click.Path(path_type=Path, file_okay=False), help="Inbox directory (default: ./inbox).")
@click.option("--model", help="Claude model (default: claude-sonnet-5-5, or IQBANK_MODEL).")
@click.option("--dry-run", is_flag=True, help="Show what would happen. No network calls, no Claude calls, nothing written.")
@click.option("-v", "--verbose", count=True, help="-v for debug logs, -vv to include HTTP libraries.")
@click.option("--log-file", type=click.Path(path_type=Path, dir_okay=False), help="Also write logs to this file.")
@click.pass_context
def main(ctx, company, roles, config_path, env_file, db_path, inbox_dir, model, dry_run, verbose, log_file):
    """Collect and organize interview questions for a target company and role."""
    setup_logging(verbose, log_file)
    try:
        settings = Settings.load(
            config_path,
            env_file,
            overrides={"company": company, "roles": roles, "db_path": db_path, "inbox_dir": inbox_dir, "model": model},
        )
    except (OSError, ValueError) as exc:
        raise click.ClickException(f"could not load settings: {exc}") from exc
    ctx.obj = App(settings=settings, dry_run=dry_run)


# ---- commands -----------------------------------------------------------------------


@main.command()
@click.option("--source", "sources", multiple=True, type=click.Choice(["reddit", "web", "github", "inbox"]),
              help="Only these sources (repeatable). Default: all configured.")
@click.option("--block", "extra_block", multiple=True, help="Extra domain to skip (repeatable).")
@dry_run_option
@click.pass_obj
def collect(app: App, sources, extra_block, local_dry_run):
    """Fetch new documents from Reddit, web search, GitHub and ./inbox/."""
    _collect(app, sources, extra_block, _is_dry(app, local_dry_run))


def _collect(app: App, sources, extra_block, dry: bool) -> None:
    from iqbank.net import HttpClient
    from iqbank.sources import build_sources
    from iqbank.sources import collect as run_collect

    app.settings.blocklist.extend(extra_block)
    with app.store(dry) as store, HttpClient(app.settings) as http:
        results = run_collect(store, build_sources(app.settings, sources, http), app.settings, dry_run=dry, echo=click.echo)
    for name, stats in results.items():
        click.echo(f"collect {name}: {stats}")


@main.command()
@click.option("--limit", type=int, help="Extract at most N documents this run.")
@click.option("--reextract", is_flag=True, help="Re-extract every document, not just new or changed ones.")
@dry_run_option
@click.pass_obj
def extract(app: App, limit, reextract, local_dry_run):
    """Extract questions from documents that are new or changed since the last run."""
    _extract(app, limit, reextract, _is_dry(app, local_dry_run))


def _extract(app: App, limit, reextract, dry: bool) -> None:
    from iqbank.extract import extract_pending

    llm = None if dry else app.llm()
    with app.store(dry) as store:
        try:
            stats = extract_pending(store, llm, app.settings, limit=limit, reextract=reextract, dry_run=dry, echo=click.echo)
        except FatalLLMError as exc:
            _fatal(exc)
    click.echo(f"extract: {stats}")
    if llm and llm.calls:
        click.echo(f"extract: {llm.usage_summary()}")


@main.command()
@click.option("--method", type=click.Choice(["claude", "lexical"]), default="claude", show_default=True,
              help="claude: semantic clustering. lexical: offline text similarity.")
@click.option("--force", is_flag=True, help="Re-cluster even if no questions changed.")
@dry_run_option
@click.pass_obj
def dedupe(app: App, method, force, local_dry_run):
    """Cluster near-duplicate questions and count independent sources."""
    _dedupe(app, method, force, _is_dry(app, local_dry_run))


def _dedupe(app: App, method, force, dry: bool) -> None:
    from iqbank.dedupe import run_dedupe

    llm = app.llm() if method == "claude" and not dry else None
    with app.store(dry) as store:
        try:
            stats = run_dedupe(store, llm, app.settings, method=method, force=force, dry_run=dry, echo=click.echo)
        except FatalLLMError as exc:
            _fatal(exc)
    click.echo(f"dedupe: {stats}")
    if llm and llm.calls:
        click.echo(f"dedupe: {llm.usage_summary()}")


@main.command()
@click.option("--out", "out_dir", type=click.Path(path_type=Path, file_okay=False), help="Output directory (default: ./out).")
@click.option("--no-llm-summary", is_flag=True, help="Loop summary from statistics only; skip the Claude narrative.")
@dry_run_option
@click.pass_obj
def report(app: App, out_dir, no_llm_summary, local_dry_run):
    """Write questions.csv, questions.md and loop_summary.md."""
    _report(app, out_dir, no_llm_summary, _is_dry(app, local_dry_run))


def _report(app: App, out_dir, no_llm_summary, dry: bool) -> None:
    from iqbank.report import generate_report

    out = out_dir or app.settings.out_dir
    llm = None if no_llm_summary or dry else app.llm()
    with app.store(dry) as store:
        try:
            paths = generate_report(store, app.settings, llm, out, dry_run=dry, echo=click.echo)
        except FatalLLMError as exc:
            _fatal(exc)
    for p in paths:
        click.echo(f"report: wrote {p}")
    if llm and llm.calls:
        click.echo(f"report: {llm.usage_summary()}")


@main.command()
@click.option("--source", "sources", multiple=True, type=click.Choice(["reddit", "web", "github", "inbox"]))
@click.option("--method", type=click.Choice(["claude", "lexical"]), default="claude", show_default=True)
@click.option("--out", "out_dir", type=click.Path(path_type=Path, file_okay=False))
@click.option("--no-llm-summary", is_flag=True)
@dry_run_option
@click.pass_obj
def run(app: App, sources, method, out_dir, no_llm_summary, local_dry_run):
    """collect -> extract -> dedupe -> report."""
    dry = _is_dry(app, local_dry_run)
    _collect(app, sources, (), dry)
    _extract(app, None, False, dry)
    _dedupe(app, method, False, dry)
    _report(app, out_dir, no_llm_summary, dry)


@main.command()
@click.pass_obj
def status(app: App):
    """Show what's in the database."""
    with app.store(True) as store:
        st = store.stats()
    s = app.settings
    click.echo(f"company: {s.company} | roles: {s.roles_label} | db: {s.db_path} | model: {s.model}")
    click.echo("docs by source: " + (", ".join(f"{k}={v}" for k, v in sorted(st["docs_by_source"].items())) or "none"))
    click.echo("extractions: " + (", ".join(f"{k}={v}" for k, v in sorted(st["extractions_by_status"].items())) or "none")
               + f" | pending: {st['pending_extraction']}")
    click.echo(f"questions: {st['questions']} ({st['unclustered_questions']} not yet clustered) | clusters: {st['clusters']}"
               f" | skipped URLs: {st['skipped_urls']}")


if __name__ == "__main__":  # pragma: no cover
    main()
