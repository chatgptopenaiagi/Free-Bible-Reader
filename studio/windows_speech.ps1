[CmdletBinding()]
param([ValidateSet('catalog','synthesize')][string]$Action='catalog',[string]$RequestPath)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
function Sapi-Voices {
    Add-Type -AssemblyName System.Speech
    $s=[System.Speech.Synthesis.SpeechSynthesizer]::new()
    try{@($s.GetInstalledVoices() | Where-Object Enabled | ForEach-Object {[ordered]@{provider='windows-sapi';id=$_.VoiceInfo.Id;name=$_.VoiceInfo.Name;language=$_.VoiceInfo.Culture.Name;gender=$_.VoiceInfo.Gender.ToString();managed=$false;installed=$true}})}finally{$s.Dispose()}
}
function Winrt-Type {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    [Windows.Media.SpeechSynthesis.SpeechSynthesizer,Windows.Media.SpeechSynthesis,ContentType=WindowsRuntime]
}
function Media-Voices {
    $type=Winrt-Type
    @($type::AllVoices | ForEach-Object {[ordered]@{provider='windows-media';id=$_.Id;name=$_.DisplayName;language=$_.Language;gender=$_.Gender.ToString();managed=$false;installed=$true}})
}
function Await-Operation($Operation,[Type]$ResultType){
    $method=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {$_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'} | Select-Object -First 1
    $task=$method.MakeGenericMethod($ResultType).Invoke($null,@($Operation))
    if(!$task.Wait(240000)){throw 'WINDOWS_SYNTHESIS_TIMEOUT'}
    $task.Result
}
try{
    if($Action -eq 'catalog'){
        $voices=@();$errors=@()
        try{$voices+=@(Sapi-Voices)}catch{$errors+=[ordered]@{provider='windows-sapi';error='NATIVE_ENUMERATION_FAILED';exception_type=$_.Exception.GetType().FullName}}
        try{$voices+=@(Media-Voices)}catch{$errors+=[ordered]@{provider='windows-media';error='NATIVE_ENUMERATION_FAILED';exception_type=$_.Exception.GetType().FullName}}
        [ordered]@{status='OK';voices=$voices;errors=$errors}|ConvertTo-Json -Depth 8 -Compress
        exit 0
    }
    $request=[IO.File]::ReadAllText($RequestPath,[Text.Encoding]::UTF8)|ConvertFrom-Json
    if(!$request.output_path -or !$request.text -or $request.text.Length -gt 25000){throw 'INVALID_SYNTHESIS_REQUEST'}
    $speed=[double]$request.speed
    if([double]::IsNaN($speed) -or [double]::IsInfinity($speed) -or $speed -lt .5 -or $speed -gt 2){throw 'INVALID_SPEED'}
    if(Test-Path -LiteralPath $request.output_path){throw 'OUTPUT_ALREADY_EXISTS'}
    if($request.provider -eq 'windows-sapi'){
        Add-Type -AssemblyName System.Speech
        $s=[System.Speech.Synthesis.SpeechSynthesizer]::new()
        try{
            $voice=@($s.GetInstalledVoices() | Where-Object {$_.Enabled -and $_.VoiceInfo.Id -eq $request.voice})
            if($voice.Count -ne 1){throw 'VOICE_NOT_AVAILABLE'}
            if(@($s.GetInstalledVoices() | Where-Object {$_.Enabled -and $_.VoiceInfo.Name -eq $voice[0].VoiceInfo.Name}).Count -ne 1){throw 'AMBIGUOUS_NATIVE_VOICE_NAME'}
            $s.SelectVoice($voice[0].VoiceInfo.Name)
            $s.Rate=[int][Math]::Round([Math]::Log($speed,2)*5)
            $s.SetOutputToWaveFile($request.output_path)
            $s.Speak([string]$request.text)
        }finally{$s.Dispose()}
    }elseif($request.provider -eq 'windows-media'){
        $type=Winrt-Type;$s=New-Object $type
        try{
            $voice=@($type::AllVoices | Where-Object Id -eq $request.voice)
            if($voice.Count -ne 1){throw 'VOICE_NOT_AVAILABLE'}
            $s.Voice=$voice[0];$s.Options.SpeakingRate=$speed
            $stream=Await-Operation ($s.SynthesizeTextToStreamAsync([string]$request.text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream,Windows.Media.SpeechSynthesis,ContentType=WindowsRuntime])
            try{
                $input=[System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream)
                $output=[IO.File]::Open($request.output_path,[IO.FileMode]::CreateNew)
                try{$input.CopyTo($output)}finally{$output.Dispose();$input.Dispose()}
            }finally{$stream.Dispose()}
        }finally{$s.Dispose()}
    }else{throw 'UNSUPPORTED_PROVIDER'}
    [ordered]@{status='OK';provider=$request.provider;voice=$request.voice;requested_speed=$speed;output_path=$request.output_path}|ConvertTo-Json -Compress
}catch{
    [ordered]@{status='ERROR';error='WINDOWS_SPEECH_FAILED';exception_type=$_.Exception.GetType().FullName;hresult=$_.Exception.HResult}|ConvertTo-Json -Compress
    exit 1
}
