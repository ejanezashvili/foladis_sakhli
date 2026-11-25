# Runs one of the manual scripts with the demo users' password in the environment (kept DPAPI-encrypted
# in %USERPROFILE%\.steelhouse\video_demo.cred - only this Windows user can read it).
#   powershell -File deploy\manual_video\run.ps1 probe.py [args]
param([Parameter(Mandatory = $true)][string]$Script, [switch]$Fast, [Parameter(ValueFromRemainingArguments = $true)]$Rest)
if ($Fast) { $env:SH_VM_FAST = '1' }
$env:SH_VM_PW = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR((Get-Content "$env:USERPROFILE\.steelhouse\video_demo.cred" | ConvertTo-SecureString)))
$env:PYTHONIOENCODING = 'utf-8'
& python (Join-Path $PSScriptRoot $Script) @Rest
exit $LASTEXITCODE
