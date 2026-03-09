param(
    [Parameter(Position = 0)]
    [ValidateSet("build", "up", "down", "test", "logs")]
    [string]$Target
)

if (-not $Target) {
    Write-Error "Usage: ./make.ps1 <build|up|down|test|logs>"
    exit 1
}

$composeArgs = switch ($Target) {
    "build" { @("build") }
    "up" { @("up", "-d") }
    "down" { @("down", "--remove-orphans") }
    "logs" { @("logs", "-f") }
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
