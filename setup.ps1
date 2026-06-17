# One-time local setup (Windows / PowerShell).
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm --prefix frontend install
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
Write-Host "Setup complete. Add your ANTHROPIC_API_KEY to backend\.env, then run .\dev.ps1"
