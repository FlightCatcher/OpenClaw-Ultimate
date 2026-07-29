
import typer
from rich.console import Console
from openclaw_ultimate.config import load_settings
from openclaw_ultimate.doctor import run_doctor
from openclaw_ultimate.models import OllamaProvider
from openclaw_ultimate.runtime import AgentRuntime

app = typer.Typer(no_args_is_help=True)
console = Console()

@app.command()
def doctor() -> None:
    raise typer.Exit(code=0 if run_doctor(load_settings()) else 1)

@app.command()
def chat() -> None:
    s = load_settings()
    runtime = AgentRuntime(OllamaProvider(s.ollama_model, s.ollama_base_url))
    console.print(f"[green]{s.app_name}[/green] · {s.ollama_model}")
    while True:
        try:
            msg = console.input("[blue]你> [/blue]").strip()
            if msg.lower() in {"/exit", "/quit"}:
                break
            console.print(f"[magenta]AI>[/magenta] {runtime.respond(msg)}")
        except KeyboardInterrupt:
            break
        except Exception as exc:
            console.print(f"[red]错误：{exc}[/red]")

if __name__ == "__main__":
    app()
