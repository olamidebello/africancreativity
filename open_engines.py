"""Self-hosted engines integrated with the existing authenticated job queue."""
import json, os, signal, subprocess, tempfile
from pathlib import Path
from database import Problem, text, number

CATALOG = {
    'ace-step': dict(name='ACE-Step · songs and instrumentals', kind='audio', ext='wav', mime='audio/wav'),
    'wan': dict(name='Wan2.1 · text to video', kind='video', ext='mp4', mime='video/mp4'),
    'flux-schnell': dict(name='FLUX.1-schnell · artwork', kind='image', ext='png', mime='image/png'),
    'whisper': dict(name='Whisper Small · transcription and subtitles', kind='text', ext='json', mime='application/json'),
    'kokoro': dict(name='Kokoro · AI narration', kind='audio', ext='wav', mime='audio/wav'),
}

def configuration():
    try:
        data=json.loads(Path(os.environ.get('OPEN_ENGINES_CONFIG',str(Path(__file__).parent/'open-engines.json'))).read_text())
        return data if isinstance(data,dict) else {}
    except (OSError,ValueError): return {}

def catalog():
    conf=configuration()
    return [dict(id=k, **v, ready=bool(conf.get(k,{}).get('verified')) and Path(conf.get(k,{}).get('python','/nonexistent')).is_file()) for k,v in CATALOG.items()]

def validate(p):
    engine=p.get('engine')
    if engine not in CATALOG: raise Problem('Unknown self-hosted engine')
    result={'engine':engine,'prompt':text(p,'prompt',2000,required=engine!='whisper'),'seed':int(number(p.get('seed',0),0,2147483647))}
    if engine=='ace-step':
        result.update(lyrics=text(p,'lyrics',4000,required=False),duration=number(p.get('duration',15),5,60))
    if engine=='kokoro':
        result.update(voice=p.get('voice','af_heart'),speed=number(p.get('speed',1),.5,2))
        if result['voice'] not in ('af_heart','af_bella','am_adam','bf_emma','bm_george'): raise Problem('Unsupported Kokoro voice')
    if engine=='whisper':
        result['asset_id']=int(number(p.get('asset_id'),1,2147483647))
    if engine=='wan':
        result['aspect']=p.get('aspect','16:9')
        if result['aspect'] not in ('16:9','9:16'): raise Problem('Choose 16:9 or 9:16')
    return result

def render(payload,out,source=None):
    p=validate(payload); config=configuration().get(p['engine'],{})
    if not any(m['id']==p['engine'] and m['ready'] for m in catalog()): raise Problem('Selected self-hosted engine has not passed installation verification',503)
    runner=Path(__file__).parent/'deploy'/'run_open_engine.py'
    # Credentials and arbitrary environment variables are never inherited by model code.
    env={'PATH':'/usr/bin:/bin','HOME':config['cache'],'HF_HOME':config['cache']+'/huggingface','TORCH_HOME':config['cache']+'/torch','PYTHONNOUSERSITE':'1','TOKENIZERS_PARALLELISM':'false','OMP_NUM_THREADS':'2'}
    args=[config['python'],str(runner),'--engine',p['engine'],'--output',str(out),'--cache',config['cache']]
    if p['engine']=='whisper':
        if source is None: raise Problem('Select audio or video to transcribe')
        args+=['--source',str(source)]
    with tempfile.TemporaryDirectory(prefix='creation-inference-') as work:
        proc=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,cwd=work,env=env,start_new_session=True)
        try:
            proc.communicate(json.dumps(p).encode(),timeout=1800)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGKILL);proc.wait()
            raise Problem('Self-hosted generation exceeded 30 minutes; the process was stopped',504)
        if proc.returncode: raise Problem('Self-hosted generation failed. Check model installation, GPU memory and disk space.',502)
    if not Path(out).is_file() or not 16<Path(out).stat().st_size<=100*1024*1024:
        raise Problem('Self-hosted engine returned an invalid or oversized output',502)
    return CATALOG[p['engine']]
