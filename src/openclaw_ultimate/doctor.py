
import sys, httpx
from rich.console import Console
from openclaw_ultimate.config import Settings

console = Console()

def run_doctor(settings: Settings) -> bool:
    ok = True
    console.print(f"[bold]Python:[/bold] {sys.version.split()[0]}")
    if not sys.version.startswith("3.12."):
        console.print("[yellow]建议使用 Python 3.12。[/yellow]")
        ok = False
    try:
        r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3)
        r.raise_for_status()
        console.print("[green]Ollama: connected[/green]")
    except Exception as exc:
        console.print(f"[red]Ollama: unavailable ({exc})[/red]")
        ok = False
    return ok
