# ====================================================================
#  cible.ps1 - A lancer sur le PC HOTE (celui qui fait tourner Docker)
#  Affiche l'IP Wi-Fi du moment + les commandes a copier sur le PC Attaquant.
#
#  Lancement (clic droit > Executer avec PowerShell), ou dans un terminal :
#     powershell -ExecutionPolicy Bypass -File attack\cible.ps1
# ====================================================================

# IP IPv4 de la carte Wi-Fi (fiable, via l'API reseau de Windows - pas de parsing texte)
$ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
        $_.IPAddress -notlike '169.254.*' -and
        $_.IPAddress -ne '127.0.0.1' -and
        (Get-NetAdapter -InterfaceIndex $_.InterfaceIndex -ErrorAction SilentlyContinue).Name -match 'Wi-?Fi|sans fil|Wireless'
    } | Select-Object -First 1 -ExpandProperty IPAddress)

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
if (-not $ip) {
    Write-Host "  IP Wi-Fi introuvable. Es-tu bien connecte en Wi-Fi ?" -ForegroundColor Red
    Write-Host "  Sinon lance 'ipconfig' et prends 'Adresse IPv4' sous Wi-Fi."
    Write-Host "============================================================" -ForegroundColor Cyan
    Read-Host "Entree pour fermer"
    exit 1
}
Write-Host "  IP de CE PC (le PC Hote / cible) :  $ip" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Sur le PC ATTAQUANT, copie ces commandes :"
Write-Host ""
Write-Host "  1) Verifier que les 2 PC se voient :"
Write-Host "       curl http://$($ip):8000/health" -ForegroundColor Yellow
Write-Host "     (doit repondre {`"status`":`"ok`"})"
Write-Host ""
Write-Host "  2) Attaque principale (flood) :"
Write-Host "       python3 flood.py --target http://$($ip):8000 --duration 40 --concurrency 120" -ForegroundColor Yellow
Write-Host ""
Write-Host "  3) Injection SQL (doit etre bloquee, code 403) :"
Write-Host "       bash sqli.sh http://$($ip):8000" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Dashboard (sur ce PC) : http://localhost:3000"
Write-Host "  Grafana (courbes)     : http://localhost:3001"
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Verifie au passage que l'API repond bien sur cette IP depuis l'hote
try {
    $r = Invoke-WebRequest -Uri "http://$($ip):8000/health" -TimeoutSec 5 -UseBasicParsing
    if ($r.StatusCode -eq 200) { Write-Host "  [OK] L'API repond sur $ip (cote hote). Pret pour la demo." -ForegroundColor Green }
} catch {
    Write-Host "  [!] L'API ne repond pas encore sur $ip. Lance d'abord : docker compose up -d" -ForegroundColor Red
}
Write-Host ""
Read-Host "Entree pour fermer"
