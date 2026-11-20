# Installs (or updates) the course tools on Windows from PowerShell:
#   powershell -ExecutionPolicy Bypass -c "irm https://github.com/alvarobernal2412/hs-marimo26/releases/latest/download/install.ps1 | iex"
# Everything is fetched by PowerShell, never by a browser, so Windows puts no "downloaded from the internet" mark on it.
# The package goes to %USERPROFILE%\hs-marimo26 and starts; later, double-click Start in that folder (or run this line again).
# Overrides, for tests: HS_PACKAGE_URL (a zip's URL or a local file), HS_DEST (the folder), HS_NO_START=1 (install, do not start).

function Install-HsMarimo {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'  # Windows PowerShell 5.1 downloads many times faster without its progress bar
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $repo = 'alvarobernal2412/hs-marimo26'
    $dest = if ($env:HS_DEST) { $env:HS_DEST } else { Join-Path $env:USERPROFILE 'hs-marimo26' }
    $url = $env:HS_PACKAGE_URL
    if (-not $url) {
        Write-Host 'Looking for the latest version of the course tools...'
        # the public "latest release" page redirects to .../tag/<version>: no API call, so no rate limit for a whole classroom
        $request = [Net.HttpWebRequest]::Create("https://github.com/$repo/releases/latest")
        $request.AllowAutoRedirect = $false
        $response = $request.GetResponse()
        $location = $response.Headers['Location']
        $response.Close()
        if ($location -notmatch '/tag/(v\d[^/]*)$') { throw 'Could not find the latest version. Check your internet connection and try again.' }
        $tag = $Matches[1]
        $url = "https://github.com/$repo/releases/download/$tag/hs-marimo26-$tag-windows-x64.zip"
    }
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ('hs-marimo26-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        $zip = Join-Path $tmp 'package.zip'
        Write-Host 'Downloading the course tools (this can take a few minutes)...'
        if (Test-Path -LiteralPath $url -PathType Leaf) { Copy-Item -LiteralPath $url -Destination $zip }
        else { Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $zip }
        New-Item -ItemType Directory -Path $dest -Force | Out-Null
        # only the package's own files are overwritten: anything else in the folder stays. System32's tar reads zip quickly.
        & "$env:SystemRoot\System32\tar.exe" -xf $zip -C $dest
        if ($LASTEXITCODE -ne 0) { Expand-Archive -LiteralPath $zip -DestinationPath $dest -Force }
    }
    finally {
        Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host ''
    Write-Host "The course tools are in: $dest"
    if ($env:HS_NO_START) { return }
    Write-Host 'Starting them now. Next time, double-click Start in that folder.'
    Write-Host ''
    Set-Location -LiteralPath $dest
    cmd /c "Start.bat"
}

try { Install-HsMarimo }
catch { Write-Host ''; Write-Host "Something went wrong: $($_.Exception.Message)"; Write-Host 'Please send a photo of this window to your teachers.' }
