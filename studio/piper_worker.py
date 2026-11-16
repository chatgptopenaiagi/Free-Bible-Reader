"""One bounded CPU-only Piper process; invoked by the frozen launcher or -m."""
from __future__ import annotations
import json
import pathlib
import sys
import wave

def main(request_path=None):
    from piper import PiperVoice, SynthesisConfig
    request = json.loads(pathlib.Path(request_path or sys.argv[1]).read_text(encoding='utf-8'))
    voice = PiperVoice.load(request['model_path'], config_path=request['config_path'], use_cuda=False)
    config = SynthesisConfig(length_scale=1.0 / request['speed'], volume=request.get('volume', 1.0))
    with wave.open(request['output_path'], 'wb') as output:
        voice.synthesize_wav(request['text'], output, syn_config=config)
    print(json.dumps({'status':'OK','provider':'piper','voice':request['voice'],'device':'CPU'}), flush=True)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
