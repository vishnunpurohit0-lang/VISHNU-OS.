# Launch Vishnu OS on Windows
Clear-Host
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "       Launching Vishnu Micro-OS (Rust x86_64)            " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan
Set-Location "$PSScriptRoot\.."
cargo run
