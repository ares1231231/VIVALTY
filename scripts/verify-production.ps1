# Quick production smoke test for Vivalty on Railway.
# Usage: .\scripts\verify-production.ps1
# Optional: .\scripts\verify-production.ps1 -BaseUrl https://vivalty.com

param(
    [string]$BaseUrl = "https://vivalty-production.up.railway.app"
)

$ErrorActionPreference = "Continue"
$paths = @(
    @{ Path = "/healthz/"; Expect = 200; Label = "Healthcheck" }
    @{ Path = "/"; Expect = 200; Label = "Home" }
    @{ Path = "/auth/login/"; Expect = 200; Label = "Login" }
    @{ Path = "/auth/register/"; Expect = 200; Label = "Register" }
    @{ Path = "/marketplace/"; Expect = 200; Label = "Marketplace" }
    @{ Path = "/admin/"; Expect = 302; Label = "Admin (redirect to login)" }
    @{ Path = "/static/css/tailwind.css"; Expect = 200; Label = "Tailwind CSS" }
    @{ Path = "/robots.txt"; Expect = 200; Label = "robots.txt" }
    @{ Path = "/sitemap.xml"; Expect = 200; Label = "sitemap.xml" }
)

Write-Host "Vivalty production verify - $BaseUrl`n" -ForegroundColor Cyan

$fail = 0
foreach ($item in $paths) {
    $url = "$BaseUrl$($item.Path)"
    try {
        $resp = Invoke-WebRequest -Uri $url -Method Get -UseBasicParsing -MaximumRedirection 0 -ErrorAction SilentlyContinue
        $code = [int]$resp.StatusCode
    } catch {
        if ($_.Exception.Response) {
            $code = [int]$_.Exception.Response.StatusCode.value__
        } else {
            Write-Host "[FAIL] $($item.Label) - $($item.Path) - $($_.Exception.Message)" -ForegroundColor Red
            $fail++
            continue
        }
    }
    if ($code -eq $item.Expect) {
        Write-Host "[OK]   $($item.Label) - $code" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] $($item.Label) - expected $($item.Expect), got $code" -ForegroundColor Red
        $fail++
    }
}

# Optional custom domain
$custom = "https://vivalty.com"
if ($BaseUrl -ne $custom) {
    Write-Host "`nCustom domain ($custom):" -ForegroundColor Cyan
    try {
        $r = Invoke-WebRequest -Uri "$custom/healthz/" -UseBasicParsing -TimeoutSec 15
        Write-Host "[OK]   healthz - $($r.StatusCode)" -ForegroundColor Green
    } catch {
        Write-Host "[FAIL] $custom - $($_.Exception.Message)" -ForegroundColor Red
        $fail++
    }
}

# www subdomain (often missing DNS)
Write-Host "`nwww subdomain:" -ForegroundColor Cyan
try {
    Resolve-DnsName www.vivalty.com -ErrorAction Stop | Out-Null
    $r = Invoke-WebRequest -Uri "https://www.vivalty.com/healthz/" -UseBasicParsing -TimeoutSec 15
    Write-Host "[OK]   www.vivalty.com - $($r.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "[WARN] www.vivalty.com - DNS or HTTPS not configured ($($_.Exception.Message))" -ForegroundColor Yellow
}

Write-Host ""
if ($fail -eq 0) {
    Write-Host "All critical checks passed." -ForegroundColor Green
    exit 0
} else {
    Write-Host "$fail check(s) failed." -ForegroundColor Red
    exit 1
}
