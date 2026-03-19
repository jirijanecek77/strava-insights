param(
    [Parameter(Position = 0)]
    [ValidateSet("build", "up", "down", "test", "logs", "build-prod", "up-prod", "down-prod", "logs-prod")]
    [string]$Target
)

if (-not $Target) {
    Write-Error "Usage: ./make.ps1 <build|up|down|test|logs|build-prod|up-prod|down-prod|logs-prod>"
    exit 1
}

$composeArgs = switch ($Target) {
    "build" { @("build") }
    "up" { @("up", "-d") }
    "down" { @("down", "--remove-orphans") }
    "logs" { @("logs", "-f") }
    "build-prod" { @("--env-file", ".env.production", "-f", "docker-compose.prod.yml", "build") }
    "up-prod" { @("--env-file", ".env.production", "-f", "docker-compose.prod.yml", "up", "-d") }
    "down-prod" { @("--env-file", ".env.production", "-f", "docker-compose.prod.yml", "down", "--remove-orphans") }
    "logs-prod" { @("--env-file", ".env.production", "-f", "docker-compose.prod.yml", "logs", "-f") }
    "test" { $null }
}

if ($Target -eq "test") {
    docker compose run --rm backend pytest
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    docker compose run --rm worker pytest
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    docker compose run --rm frontend npm run test -- --run
    exit $LASTEXITCODE
}

docker compose @composeArgs
exit $LASTEXITCODE
