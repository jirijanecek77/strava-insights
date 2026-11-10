param(
    [Parameter(Position = 0)]
    [ValidateSet("build", "up", "down", "test", "logs", "build-prod", "up-prod", "down-prod", "logs-prod", "ai-plan-replan")]
    [string]$Target,
    [int]$AiUserId = 1
)

if (-not $Target) {
    Write-Error "Usage: ./make.ps1 <build|up|down|test|logs|build-prod|up-prod|down-prod|logs-prod|ai-plan-replan> [-AiUserId 1]"
    exit 1
}

$composeArgs = @(switch ($Target) {
    "build" { @("--env-file", ".env.secrets", "build") }
    "up" { @("--env-file", ".env.secrets", "up", "-d") }
    "down" { @("--env-file", ".env.secrets", "down", "--remove-orphans") }
    "logs" { @("--env-file", ".env.secrets", "logs", "-f") }
    "build-prod" { @("--env-file", ".env.production", "-f", "docker-compose.prod.yml", "build") }
    "up-prod" { @("--env-file", ".env.production", "-f", "docker-compose.prod.yml", "up", "-d") }
    "down-prod" { @("--env-file", ".env.production", "-f", "docker-compose.prod.yml", "down", "--remove-orphans") }
    "logs-prod" { @("--env-file", ".env.production", "-f", "docker-compose.prod.yml", "logs", "-f") }
    "ai-plan-replan" { @("--env-file", ".env.secrets", "exec", "worker", "python", "-m", "app.coaching_cli", "replan", "--user-id", "$AiUserId") }
    "test" { $null }
})

if ($Target -eq "test") {
    docker compose --env-file .env.secrets run --rm backend pytest
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    docker compose --env-file .env.secrets run --rm worker pytest
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    docker compose --env-file .env.secrets run --rm frontend npm run test -- --run
    exit $LASTEXITCODE
}

docker compose @composeArgs
exit $LASTEXITCODE
