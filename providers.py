"""Provider calls are server-side. No synthetic output is represented as AI output."""
import os,json,urllib.request,urllib.error,importlib.util,shutil,base64,time,re
from database import Problem

def capabilities():
    key=bool(os.environ.get('OPENAI_API_KEY'))
    mg=os.environ.get('MUSICGEN_ENABLED')=='1' and os.environ.get('MUSICGEN_LICENSE_ACCEPTED')=='1' and all(importlib.util.find_spec(m) is not None for m in ('transformers','torch','scipy'))
    dm=os.environ.get('DEMUCS_ENABLED')=='1' and importlib.util.find_spec('demucs') is not None
    return dict(lyrics=key,prompt=key,storyboard=key,speech=key,music=mg,stems=dm,audio_edit=bool(shutil.which('ffmpeg')),video_render=bool(shutil.which('ffmpeg')),synth=True,
                singing=False,voice_cloning=False,custom_models=False,images=key,ai_motion_video=key and os.environ.get('VIDEO_AI_ENABLED')=='1',
                models=[{'id':'musicgen-small','name':'MusicGen Small · instrumental · optional','ready':mg},{'id':'synth','name':'Local note synthesizer · not AI','ready':True}])

def openai(path,data=None,binary=False):
    key=os.environ.get('OPENAI_API_KEY')
    if not key:raise Problem('AI is not configured. Ask the platform administrator.',503)
    req=urllib.request.Request('https://api.openai.com/v1/'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=120) as r:raw=r.read(50*1024*1024+1)
    except urllib.error.HTTPError as e:
        raise Problem('AI provider rejected the request (HTTP '+str(e.code)+'). Check quota, model access and account configuration.',502)
    except (urllib.error.URLError,TimeoutError):raise Problem('AI provider unavailable; please try again later.',502)
    if len(raw)>50*1024*1024:raise Problem('Provider output exceeds 50 MB',413)
    return raw if binary else json.loads(raw)

def assist(kind,prompt):
    instructions={
        'lyrics':'Write original song lyrics. Return only lyrics with section labels. Do not reproduce existing songs. Follow the language, theme and style requested.',
        'prompt':'Expand the idea into concise original music production directions: genre, mood, tempo, instruments, arrangement. Return only the prompt.',
        'storyboard':'Return JSON only: {"storyline":"...","scenes":[{"title":"...","prompt":"...","subtitle":"...","duration":5}]}. Create 3 to 8 original scenes, 2 to 15 seconds each. Do not claim to analyze audio: you receive text metadata only. Use the supplied theme and lyrics.'}
    result=openai('responses',dict(model=os.environ.get('OPENAI_MODEL','gpt-4.1-mini'),instructions=instructions[kind],input=prompt,max_output_tokens=1800,store=False))
    out='\n'.join(x['text'] for item in result.get('output',[]) for x in item.get('content',[]) if x.get('type')=='output_text')
    if not out:raise Problem('AI returned no text',502)
    if kind=='storyboard':
        try:
            obj=json.loads(out.strip().removeprefix('```json').removeprefix('```').removesuffix('```'))
            assert isinstance(obj['storyline'],str) and isinstance(obj['scenes'],list) and 1<=len(obj['scenes'])<=12
            for s in obj['scenes']:
                assert all(isinstance(s[k],str) for k in ('title','prompt','subtitle'))
                assert 2<=float(s['duration'])<=15
            return obj
        except (AssertionError,ValueError,KeyError,TypeError):raise Problem('AI storyboard format could not be validated. Retry.',502)
    return out

def speech(payload):
    return openai('audio/speech',dict(model=os.environ.get('OPENAI_SPEECH_MODEL','gpt-4o-mini-tts'),input=payload['text'],voice=payload.get('voice','coral'),response_format='wav'),True)

def music(payload,out):
    if not capabilities()['music']:raise Problem('MusicGen is not installed/enabled with an accepted model license',503)
    # Lazy loading avoids installing a GPU stack for tenants using only local editing.
    import torch,scipy.io.wavfile
    from transformers import AutoProcessor,MusicgenForConditionalGeneration
    processor=AutoProcessor.from_pretrained('facebook/musicgen-small')
    model=MusicgenForConditionalGeneration.from_pretrained('facebook/musicgen-small',use_safetensors=True)
    device='cuda' if torch.cuda.is_available() else 'cpu';model.to(device)
    inputs=processor(text=[payload['prompt']],padding=True,return_tensors='pt').to(device)
    with torch.no_grad():
        values=model.generate(**inputs,do_sample=True,temperature=payload.get('temperature',1),guidance_scale=payload.get('guidance',3),max_new_tokens=int(payload['duration']*50))
    scipy.io.wavfile.write(out,model.config.audio_encoder.sampling_rate,values[0,0].cpu().numpy())


def image(payload):
    result=openai('images/generations',dict(model=os.environ.get('OPENAI_IMAGE_MODEL','gpt-image-1'),prompt=payload['prompt'],size='1024x1024',quality='low',n=1,output_format='png'))
    try:raw=base64.b64decode(result['data'][0]['b64_json'],validate=True)
    except (KeyError,ValueError,IndexError):raise Problem('Image provider returned no image',502)
    if not raw.startswith(b'\x89PNG\r\n\x1a\n'):raise Problem('Invalid generated image',502)
    return raw

def motion(payload,report):
    if not capabilities()['ai_motion_video']:raise Problem('AI motion video is not enabled by the operator',503)
    result=openai('videos',dict(model='sora-2',prompt=payload['prompt'],seconds='4',size='720x1280' if payload.get('aspect')=='9:16' else '1280x720'))
    vid=result.get('id','')
    if not re.fullmatch('[a-zA-Z0-9_-]{1,200}',vid):raise Problem('Video provider returned an invalid job identifier',502)
    report(vid)
    for _ in range(90):
        if result.get('status')=='completed':return openai('videos/'+vid+'/content',binary=True)
        if result.get('status')=='failed':raise Problem('Video provider could not generate this scene. Check the prompt and provider content rules.',502)
        time.sleep(10);result=openai('videos/'+vid)
    raise Problem('Video generation timed out. The provider job may still finish; ask the operator to inspect the recorded provider job ID before retrying.',504)
