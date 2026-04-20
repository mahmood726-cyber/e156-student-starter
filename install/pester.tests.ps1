#Requires -Version 5.1
#Requires -Modules @{ ModuleName='Pester'; ModuleVersion='5.0.0' }

BeforeAll {
    $script:InstallPs1 = Join-Path $PSScriptRoot 'install.ps1'
}

Describe 'install.ps1 self-SHA verification' {
    It 'exits 1 when HASH.txt is absent' {
        $tmp = New-Item -ItemType Directory -Path (Join-Path $env:TEMP "e156-test-$(Get-Random)")
        $instDir = New-Item -ItemType Directory -Path (Join-Path $tmp 'install')
        Copy-Item $script:InstallPs1 $instDir
        $proc = Start-Process -FilePath 'powershell.exe' `
            -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',
                          (Join-Path $instDir 'install.ps1'),'-DryRun' `
            -Wait -NoNewWindow -PassThru
        $proc.ExitCode | Should -Be 1
        Remove-Item $tmp -Recurse -Force
    }

    It 'exits 1 on SHA mismatch' {
        $tmp = New-Item -ItemType Directory -Path (Join-Path $env:TEMP "e156-test-$(Get-Random)")
        $instDir = New-Item -ItemType Directory -Path (Join-Path $tmp 'install')
        $docsDir = New-Item -ItemType Directory -Path (Join-Path $tmp 'docs')
        Copy-Item $script:InstallPs1 $instDir
        Set-Content (Join-Path $docsDir 'HASH.txt') ('deadbeef' * 8) -NoNewline
        $proc = Start-Process -FilePath 'powershell.exe' `
            -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',
                          (Join-Path $instDir 'install.ps1'),'-DryRun' `
            -Wait -NoNewWindow -PassThru
        $proc.ExitCode | Should -Be 1
        Remove-Item $tmp -Recurse -Force
    }
}

Describe 'install.ps1 tier detection' {
    It 'picks 4GB tier when RAM < 6' {
        . $script:InstallPs1 -Import
        $tier = Select-Tier -RamGb 4
        $tier.ProseModel | Should -BeNullOrEmpty
        $tier.CloudOnly | Should -Be $true
    }

    It 'picks small-model tier for 8 GB' {
        . $script:InstallPs1 -Import
        $tier = Select-Tier -RamGb 8
        $tier.ProseModel | Should -Be 'gemma2:2b'
        $tier.CodeModel  | Should -Be 'qwen2.5-coder:1.5b'
    }

    It 'picks big-model tier for 16 GB' {
        . $script:InstallPs1 -Import
        $tier = Select-Tier -RamGb 16
        $tier.ProseModel | Should -Be 'gemma2:9b'
        $tier.CodeModel  | Should -Be 'qwen2.5-coder:7b'
    }
}

Describe 'install.ps1 rollback on partial failure' {
    It 'removes ~/e156/ if Ollama pull fails' {
        $tmpLocalAppData = Join-Path $env:TEMP "e156-rollback-$(Get-Random)"
        New-Item $tmpLocalAppData -ItemType Directory | Out-Null
        $env:LOCALAPPDATA = $tmpLocalAppData
        . $script:InstallPs1 -Import
        $e156 = Join-Path $tmpLocalAppData 'e156'
        $logs = Join-Path $e156 'logs'
        New-Item $logs -ItemType Directory -Force | Out-Null
        'partial' | Out-File (Join-Path $logs 'install.log')
        Invoke-Rollback -E156Root $e156 -Reason 'test'
        Test-Path $e156 | Should -Be $false
        Remove-Item $tmpLocalAppData -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Describe 'install.ps1 Ollama pull with retry + SHA verify' {
    It 'retries on transient failure up to 3 times' {
        . $script:InstallPs1 -Import
        $script:attempts = 0
        $pullFn = {
            $script:attempts++
            if ($script:attempts -lt 3) { return $false } else { return $true }
        }
        $result = Invoke-OllamaPullWithRetry -Model 'gemma2:2b' `
                     -ExpectedDigest 'sha256:abc' `
                     -PullFn $pullFn -MaxAttempts 3
        $script:attempts | Should -Be 3
        $result | Should -Be $true
    }

    It 'fails after MaxAttempts' {
        . $script:InstallPs1 -Import
        $alwaysFail = { $false }
        $result = Invoke-OllamaPullWithRetry -Model 'gemma2:2b' `
                     -ExpectedDigest 'sha256:xxx' `
                     -PullFn $alwaysFail -MaxAttempts 2
        $result | Should -Be $false
    }
}

Describe 'install.ps1 smoke-gated banner' {
    It 'prints INSTALL COMPLETE only when smoke_test exit 0' {
        . $script:InstallPs1 -Import
        $banner = Get-BannerForSmokeExit -ExitCode 0
        $banner | Should -Match 'INSTALL COMPLETE'
    }

    It 'suppresses INSTALL COMPLETE when smoke_test exits nonzero' {
        . $script:InstallPs1 -Import
        $banner = Get-BannerForSmokeExit -ExitCode 1
        $banner | Should -Not -Match 'INSTALL COMPLETE'
        $banner | Should -Match "didn't start|didn.t start"
    }
}
