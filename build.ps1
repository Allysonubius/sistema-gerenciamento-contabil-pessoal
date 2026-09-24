<#
    Gera o executável SistemaContabil.exe (arquivo único, sem console).

    Uso:
        .\build.ps1
        .\build.ps1 -Portable      # o banco fica na pasta do .exe
        .\build.ps1 -PularTestes   # compila sem rodar a suite de testes
#>
param(
    [switch]$Portable,
    [switch]$PularTestes
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> Instalando dependencias..." -ForegroundColor Cyan
python -m pip install --disable-pip-version-check -r requirements.txt | Out-Null

# Um erro nas regras de negocio nao pode chegar ao executavel.
if (-not $PularTestes) {
    Write-Host "==> Rodando os testes..." -ForegroundColor Cyan
    python -m pytest tests -q
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Testes falharam: o executavel nao foi gerado." -ForegroundColor Red
        exit 1
    }
}

Write-Host "==> Gerando icone..." -ForegroundColor Cyan
python -c @'
from app.tray import criar_imagem
img = criar_imagem(256)
img.save("icone.ico", sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
print("icone.ico gerado")
'@

Write-Host "==> Compilando com PyInstaller..." -ForegroundColor Cyan
python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name SistemaContabil `
    --icon icone.ico `
    --hidden-import pystray._win32 `
    --hidden-import PIL._tkinter_finder `
    --exclude-module numpy `
    --exclude-module pandas `
    --exclude-module matplotlib `
    main.py

$exe = Join-Path $PSScriptRoot "dist\SistemaContabil.exe"
if (-not (Test-Path $exe)) {
    Write-Host "Falha: executavel nao gerado." -ForegroundColor Red
    exit 1
}

if ($Portable) {
    New-Item -ItemType File -Path (Join-Path $PSScriptRoot "dist\portable.flag") -Force | Out-Null
    Write-Host "Modo portatil habilitado (dados em dist\dados)." -ForegroundColor Yellow
}

$tamanho = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "==> Pronto: $exe ($tamanho MB)" -ForegroundColor Green
