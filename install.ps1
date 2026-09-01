# install.ps1 —— install gfreport-renew-skill to native tool paths (Windows PowerShell)
# Idempotent: re-running overwrites symlinks/junctions without data loss.
[CmdletBinding()]
param(
  [string]$SkillDir = $PSScriptRoot
)

$ErrorActionPreference = 'Stop'
$SkillName = Split-Path -Leaf $SkillDir

# Tier 1 native install paths (Windows locations)
$targets = @(
  "$env:USERPROFILE\.claude\skills",
  "$env:USERPROFILE\.config\opencode\skills",
  "$env:APPDATA\Cursor\User\skills",
  "$env:USERPROFILE\.config\Codex\skills",
  "$env:APPDATA\goose\skills",
  "$env:USERPROFILE\.config\Roo-Code\skills",
  "$env:USERPROFILE\.config\Cline\skills",
  "$env:USERPROFILE\.config\Kilo\skills",
  "$env:USERPROFILE\.config\Kiro\skills",
  "$env:USERPROFILE\.config\Factory\skills",
  "$env:USERPROFILE\.config\Antigravity\skills",
  "$env:USERPROFILE\.gemini\skills"
)

# Universal fallback
$universal = "$env:USERPROFILE\.agents\skills"

$installed = 0
foreach ($target in $targets) {
  $parent = Split-Path -Parent $target
  if (-not (Test-Path $parent)) {
    # Skip if parent directory doesn't exist and isn't a standard location we expect to create
    if ($parent -like "*$env:USERPROFILE*") {
      New-Item -ItemType Directory -Path $target -Force -ErrorAction SilentlyContinue | Out-Null
    } else {
      continue
    }
  } else {
    New-Item -ItemType Directory -Path $target -Force | Out-Null
  }

  $linkPath = Join-Path $target $SkillName
  if (Test-Path $linkPath) { Remove-Item $linkPath -Recurse -Force }

  # Junction works without admin; falls back to copy if junction fails
  $cmd = "New-Item -ItemType Junction -Path '$linkPath' -Target '$SkillDir' -Force"
  try {
    Invoke-Expression $cmd
    Write-Host "  ✓ linked $linkPath"
    $installed++
  } catch {
    Copy-Item -Path $SkillDir -Destination $linkPath -Recurse -Force
    Write-Host "  ✓ copied $linkPath (junction failed)"
    $installed++
  }
}

New-Item -ItemType Directory -Path $universal -Force | Out-Null
$linkPath = Join-Path $universal $SkillName
if (Test-Path $linkPath) { Remove-Item $linkPath -Recurse -Force }
try {
  New-Item -ItemType Junction -Path $linkPath -Target $SkillDir -Force | Out-Null
  Write-Host "  ✓ linked $linkPath (universal fallback)"
  $installed++
} catch {
  Copy-Item -Path $SkillDir -Destination $linkPath -Recurse -Force
  Write-Host "  ✓ copied $linkPath"
  $installed++
}

Write-Host ""
Write-Host "gfreport-renew-skill installed to $installed location(s)."
Write-Host "Run:  python $SkillDir\scripts\run_pipeline.py --help"