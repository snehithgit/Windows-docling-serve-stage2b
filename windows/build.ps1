# Build on Windows x64 with internet. Installed application works offline.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$build = Join-Path $root "build"
$payload = Join-Path $build "payload"
$runtime = Join-Path $payload "runtime"
$models = Join-Path $payload "models"
$stage2b = Join-Path $payload "stage2b"
$dist = Join-Path $root "dist"
$sha = "b23ed0bd81b9f8cad153f9d0d3582e7166d7a611"
$ProgressPreference = "SilentlyContinue"
New-Item -ItemType Directory -Force -Path $build, $payload, $runtime, $models, $dist | Out-Null

Write-Host "[1/9] Fetching pinned upstream Stage-2B"
git clone --quiet https://github.com/snehithgit/docling-stage2b.git $stage2b
if ($LASTEXITCODE -ne 0) { throw "Stage-2B clone failed" }
git -C $stage2b checkout --quiet $sha
if ($LASTEXITCODE -ne 0) { throw "Stage-2B checkout failed" }
if ((git -C $stage2b rev-parse HEAD).Trim() -ne $sha) { throw "Stage-2B commit differs from pinned SHA" }
Remove-Item -Force -Recurse (Join-Path $stage2b ".git")
$sha | Set-Content (Join-Path $payload "STAGE2B_UPSTREAM_COMMIT.txt") -Encoding ascii

Write-Host "[2/9] Installing portable relocatable Python"
$nugetRoot = Join-Path $build "nuget"
New-Item -ItemType Directory -Force -Path $nugetRoot | Out-Null
nuget install python -Version 3.11.9 -OutputDirectory $nugetRoot -ExcludeVersion -NonInteractive
if ($LASTEXITCODE -ne 0) { throw "Python NuGet acquisition failed" }
$tools = Join-Path $nugetRoot "python\tools"
if (-not (Test-Path (Join-Path $tools "python.exe")) -or -not (Test-Path (Join-Path $tools "pythonw.exe"))) { throw "Portable Python runtime missing" }
Copy-Item -Path (Join-Path $tools "*") -Destination $runtime -Recurse -Force
$py = Join-Path $runtime "python.exe"
& $py -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) { throw "ensurepip failed" }
& $py -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw "pip bootstrap failed" }

Write-Host "[3/9] Installing CPU-only PyTorch"
& $py -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchvision
if ($LASTEXITCODE -ne 0) { throw "CPU PyTorch installation failed" }

Write-Host "[4/9] Installing Docling Serve, Stage-2B, WebView and RAG engine"
& $py -m pip install --no-cache-dir --prefer-binary "docling-serve[ui]" "docling[easyocr,rapidocr]" sentence-transformers pywebview pythonnet -r (Join-Path $stage2b "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
& $py -m pip check
if ($LASTEXITCODE -ne 0) { throw "Python dependency conflict" }

Write-Host "[5/9] Preloading document layout, table, OCR and picture models"
New-Item -ItemType Directory -Force -Path (Join-Path $models "docling"), (Join-Path $models "hf-home"), (Join-Path $models "embedding") | Out-Null
$env:HF_HOME = Join-Path $models "hf-home"
$env:DOCLING_ARTIFACTS_PATH = Join-Path $models "docling"
$download = Join-Path $runtime "Scripts\docling-tools.exe"
if (-not (Test-Path $download)) { throw "docling-tools.exe missing" }
& $download models download layout tableformer picture_classifier code_formula easyocr rapidocr --easyocr-lang en --output-dir (Join-Path $models "docling")
if ($LASTEXITCODE -ne 0) { throw "Offline Docling model prefetch failed" }

Write-Host "[6/9] Preloading RAG embedding model and chunking tokenizer"
$preload = @'
from pathlib import Path
import os
from sentence_transformers import SentenceTransformer
from huggingface_hub import snapshot_download
root = Path(os.environ["BUNDLE_MODELS"])
m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
m.save(str(root / "embedding"))
snapshot_download("sentence-transformers/all-MiniLM-L6-v2")
assert (root / "embedding" / "modules.json").is_file()
'@
$env:BUNDLE_MODELS = $models
$preloadFile = Join-Path $build "preload.py"
$preload | Set-Content $preloadFile -Encoding utf8
& $py $preloadFile
if ($LASTEXITCODE -ne 0) { throw "Offline RAG model prefetch failed" }

Write-Host "[7/9] Copying desktop app and verified offline WebView2 runtime"
New-Item -ItemType Directory -Force -Path (Join-Path $payload "windows"), (Join-Path $payload "support") | Out-Null
Copy-Item (Join-Path $root "windows\launcher.py") (Join-Path $payload "windows\launcher.py")
Copy-Item (Join-Path $root "windows\embedding_service.py") (Join-Path $payload "windows\embedding_service.py")
$webview = Join-Path $payload "support\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
Invoke-WebRequest -Uri "https://go.microsoft.com/fwlink/?linkid=2124701" -OutFile $webview -MaximumRedirection 10
if ((Get-Item $webview).Length -lt 20000000) { throw "WebView2 installer is suspiciously small" }
$signature = Get-AuthenticodeSignature $webview
if ($signature.Status -ne "Valid" -or $signature.SignerCertificate.Subject -notmatch "Microsoft") {
    throw "WebView2 installer has invalid Microsoft digital signature"
}
$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { throw "C# desktop launcher compiler not found" }
& $csc /nologo /target:winexe /r:System.Windows.Forms.dll /r:System.Drawing.dll /out:"$payload\DoclingStage2B.exe" (Join-Path $root "windows\DoclingStage2B.cs")
if ($LASTEXITCODE -ne 0) { throw "Desktop launcher compile failed" }

Write-Host "[8/9] Verifying offline services, conversion and embedding"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:DOCLING_SERVE_ARTIFACTS_PATH = Join-Path $models "docling"
$env:PYTHONPATH = $payload
& $py (Join-Path $root "windows\smoke_test.py") $payload
if ($LASTEXITCODE -ne 0) { throw "Offline smoke test failed" }

Write-Host "[9/9] Compiling offline Inno Setup installer"
$iscc = Join-Path ([Environment]::GetFolderPath("ProgramFilesX86")) "Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) { throw "Inno Setup 6 is missing" }
& $iscc "/DPayloadDir=$payload" "/DOutputDir=$dist" "/DAppVersion=0.1.0" (Join-Path $root "windows\installer.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
$installer = Join-Path $dist "Docling-Stage2B-Offline-Setup.exe"
if (-not (Test-Path $installer)) { throw "Offline installer was not produced" }
Write-Host "SUCCESS: $installer"
