"""Velmo 2.0 Agent — Interactive REPL for conversational testing."""
import click
from agent.agent import VelmoAgent


@click.command()
def cli():
    """Velmo 2.0 Agent — Interactive support assistant."""
    click.echo("Welcome to Velmo 2.0 Agent")
    click.echo("Commands: 'user_id <id>', 'msg <message>', 'quit'")

    agent = VelmoAgent()
    user_id = None
    turn_count = 0

    while True:
        try:
            cmd = click.prompt("> ").strip()

            if cmd.startswith("quit"):
                click.echo("Goodbye.")
                break

            if cmd.startswith("user_id "):
                user_id = cmd[8:].strip()
                click.echo(f"User: {user_id}")
                turn_count = 0
                continue

            if cmd.startswith("msg "):
                if not user_id:
                    click.echo("ERROR: Set user_id first (user_id <id>)")
                    continue

                message = cmd[4:].strip()
                click.echo(f"[Processing...]")

                response = agent.process_message(user_id, message)

                click.echo(f"[Input Guard] {'allowed' if response.allowed else 'blocked'}")
                if response.guard_decision:
                    click.echo(f"  Category: {response.guard_decision.category}")
                    click.echo(f"  Reason: {response.guard_decision.reason}")

                short_term_count = len(response.memory_context.get("short_term", []))
                long_term_count = len(response.memory_context.get("long_term", []))
                click.echo(f"[Memory] short_term: {short_term_count} turns, long_term: {long_term_count} facts")

                if response.allowed:
                    click.echo(f"[Output Guard] allowed")
                else:
                    click.echo(f"[Output Guard] blocked: {response.guard_decision.category}")

                turn_mod = response.turn_number % 5
                judge_msg = f"Turn {response.turn_number}/5 to judge trigger" if turn_mod != 0 else f"Turn {response.turn_number} — JUDGE EXTRACTION TRIGGERED"
                click.echo(f"[{judge_msg}]")

                click.echo(f"\n{response.message}\n")
                click.echo(f"[Latency: {response.latency_ms}ms]\n")

                turn_count += 1

        except KeyboardInterrupt:
            click.echo("\nGoodbye.")
            break
        except Exception as e:
            click.echo(f"ERROR: {e}")


if __name__ == "__main__":
    cli()
