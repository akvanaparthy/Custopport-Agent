# Run backend + frontend in separate windows (Windows / PowerShell).
$root = $PSScriptRoot
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$root'; backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8000"
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$root'; npm --prefix frontend run dev"
Write-Host "Backend :8000 - Frontend :5173 - open http://localhost:5173"
