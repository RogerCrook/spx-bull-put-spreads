# Runs the four "on" runs (broken quotes skipped, rule fixed 2026-10-25), two at
# a time (the mid and the cross run of one case side by side), as run_count.ps1.
# Each run writes its own log in logs\.
# Start from this folder:  powershell -File run_on.ps1

$here = "C:\Dokumente\Python\Masterarbeit\experiments\quote_filter"
Set-Location $here

foreach ($case in @("base", "p15")) {
    $started = @()                              # the two processes of this case
    foreach ($execution in @("mid", "cross")) {
        $name = $case + "_" + $execution + "_on"
        # -PassThru gives back the process, so we can wait for it below
        $started += Start-Process -FilePath python -ArgumentList "-u", "run_variants.py", $name `
            -WorkingDirectory $here -RedirectStandardOutput "logs\log_$name.txt" `
            -RedirectStandardError "logs\err_$name.txt" -WindowStyle Hidden -PassThru
    }
    $started | Wait-Process                     # wait until both runs of this case are done
    Write-Output ((Get-Date -Format "HH:mm:ss") + " finished " + $case)
}
Write-Output "all on runs finished"
