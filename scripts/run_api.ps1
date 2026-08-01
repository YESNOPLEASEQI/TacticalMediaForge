param(
    [string]$ListenAddress = "127.0.0.1",
    [int]$Port = 8000
)

$signature = @'
using System;
using System.Runtime.InteropServices;

public static class ConsoleInputMode
{
    public const int STD_INPUT_HANDLE = -10;
    public const uint ENABLE_QUICK_EDIT_MODE = 0x0040;
    public const uint ENABLE_EXTENDED_FLAGS = 0x0080;

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern IntPtr GetStdHandle(int nStdHandle);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GetConsoleMode(IntPtr hConsoleHandle, out uint lpMode);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool SetConsoleMode(IntPtr hConsoleHandle, uint dwMode);
}
'@

try {
    Add-Type -TypeDefinition $signature -ErrorAction Stop
    $inputHandle = [ConsoleInputMode]::GetStdHandle(
        [ConsoleInputMode]::STD_INPUT_HANDLE
    )
    $inputMode = [uint32]0
    if ([ConsoleInputMode]::GetConsoleMode($inputHandle, [ref]$inputMode)) {
        $inputMode = (
            ($inputMode -band (-bnot [ConsoleInputMode]::ENABLE_QUICK_EDIT_MODE)) `
            -bor [ConsoleInputMode]::ENABLE_EXTENDED_FLAGS
        )
        if (-not [ConsoleInputMode]::SetConsoleMode($inputHandle, $inputMode)) {
            Write-Warning "Could not disable console QuickEdit mode."
        }
    }
} catch {
    Write-Warning "Could not configure console input mode: $($_.Exception.Message)"
}

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

# Research uses direct-reachable search engines by default. Do not make the
# entire API process depend on a desktop Clash instance merely because its port
# happens to be open. Provider-specific proxy settings remain available in
# config.yaml when an individual external API genuinely requires one.
$localProxy = "http://127.0.0.1:7890"
if ($env:HTTP_PROXY -eq $localProxy -or $env:HTTPS_PROXY -eq $localProxy) {
    Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue
    Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue
    Remove-Item Env:ALL_PROXY -ErrorAction SilentlyContinue
    Write-Host "Ignoring inherited Clash proxy; API will use provider-specific settings."
}

& uv run python api/app.py --host $ListenAddress --port $Port
exit $LASTEXITCODE
