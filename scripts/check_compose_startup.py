"""Read-only regression: no AI worker/scheduler may start before migrations finish."""

import json
import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    for filename in ("docker-compose.yml", "docker-compose.prod.yml"):
        result = subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                ".env.secrets",
                "-f",
                filename,
                "config",
                "--format",
                "json",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        configuration = json.loads(result.stdout)
        for name in ("worker", "beat", "sync-dispatcher"):
            dependencies = configuration["services"][name]["depends_on"]
            assert (
                dependencies.get("backend", {}).get("condition") == "service_healthy"
            ), f"{filename}: {name} can start before migrations finish"
        print(
            f"{filename}: worker, beat and dispatcher wait for healthy migrated backend"
        )


if __name__ == "__main__":
    main()
