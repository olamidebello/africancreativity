"""Isolated model runner. Only trusted server configuration selects executables."""
import argparse, fcntl, json, os, subprocess, sys, tempfile
from pathlib import Path

def generate(engine,p,out,cache,source=None):
    if engine=='whisper':
        from faster_whisper import WhisperModel
        model=WhisperModel('small',device='cpu',compute_type='int8',download_root=str(cache/'whisper'))
        segments,info=model.transcribe(str(source),beam_size=5,vad_filter=True)
        rows=[dict(start=float(s.start),end=float(s.end),text=s.text.strip()) for s in segments]
        def stamp(value):
            ms=round(max(0,value)*1000);seconds,ms=divmod(ms,1000);minutes,seconds=divmod(seconds,60);hours,minutes=divmod(minutes,60)
            return f'{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}'
        srt='\n\n'.join(f"{i+1}\n{stamp(s['start'])} --> {stamp(s['end'])}\n{s['text']}" for i,s in enumerate(rows))
        out.write_text(json.dumps(dict(text=' '.join(s['text'] for s in rows),srt=srt,language=info.language),ensure_ascii=False))
        return
    import torch
    torch.manual_seed(int(p.get('seed',0)))
    cuda=torch.cuda.is_available()
    if engine!='kokoro' and not cuda: raise RuntimeError('This installation profile requires CUDA for this engine')
    dtype=torch.bfloat16 if cuda and torch.cuda.is_bf16_supported() else torch.float16
    if engine=='kokoro':
        import numpy as np, soundfile as sf
        from kokoro import KPipeline
        voice=p.get('voice','af_heart')
        pipe=KPipeline(lang_code=voice[0],device='cpu')
        chunks=[audio.cpu().numpy() if hasattr(audio,'cpu') else audio for _,_,audio in pipe(p['prompt'],voice=voice,speed=p.get('speed',1))]
        if not chunks: raise RuntimeError('No narration generated')
        sf.write(out,np.concatenate(chunks),24000,subtype='PCM_16')
    elif engine=='flux-schnell':
        from diffusers import FluxPipeline
        pipe=FluxPipeline.from_pretrained('black-forest-labs/FLUX.1-schnell',torch_dtype=dtype,use_safetensors=True)
        pipe.enable_model_cpu_offload()
        pipe(p['prompt'],height=512,width=512,guidance_scale=0.,num_inference_steps=4,max_sequence_length=256,generator=torch.Generator('cpu').manual_seed(p.get('seed',0))).images[0].save(out)
    elif engine=='wan':
        from diffusers import WanPipeline, AutoencoderKLWan
        from diffusers.utils import export_to_video
        model='Wan-AI/Wan2.1-T2V-1.3B-Diffusers'
        vae=AutoencoderKLWan.from_pretrained(model,subfolder='vae',torch_dtype=torch.float32)
        pipe=WanPipeline.from_pretrained(model,vae=vae,torch_dtype=dtype,use_safetensors=True)
        pipe.enable_model_cpu_offload()
        pipe.vae.enable_tiling()
        h,w=(480,832) if p.get('aspect','16:9')=='16:9' else (832,480)
        frames=pipe(prompt=p['prompt'],height=h,width=w,num_frames=33,num_inference_steps=30,guidance_scale=5.,generator=torch.Generator('cpu').manual_seed(p.get('seed',0))).frames[0]
        export_to_video(frames,str(out),fps=16)
    elif engine=='ace-step':
        from acestep.pipeline_ace_step import ACEStepPipeline
        pipe=ACEStepPipeline(checkpoint_dir=str(cache/'ace-checkpoints'),dtype='bfloat16' if dtype==torch.bfloat16 else 'float32',cpu_offload=True)
        with tempfile.TemporaryDirectory(prefix='ace-output-') as work:
            raw=Path(work)/'song.wav'
            pipe(format='wav',audio_duration=p.get('duration',15),prompt=p['prompt'],lyrics=p.get('lyrics','') or '[instrumental]',infer_step=27,guidance_scale=15.,manual_seeds=[p.get('seed',0)],save_path=str(raw),batch_size=1)
            subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-i',str(raw),'-t',str(p.get('duration',15)),'-c:a','pcm_s16le',str(out)],check=True,timeout=90)
    else: raise ValueError('Unknown engine')

def verify(out,engine):
    if not out.is_file() or not 16<out.stat().st_size<=100*1024*1024: raise RuntimeError('Missing or oversized model output')
    if engine=='whisper':
        data=json.loads(out.read_text())
        if not isinstance(data.get('text'),str) or not isinstance(data.get('srt'),str): raise RuntimeError('Invalid transcript')
        return
    if engine=='flux-schnell':
        from PIL import Image
        with Image.open(out) as image:
            image.verify()
        return
    probe=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type','-of','json',str(out)],capture_output=True,check=True,timeout=30)
    info=json.loads(probe.stdout)
    expected='video' if engine=='wan' else 'audio'
    if float(info['format']['duration'])<=0 or not any(s['codec_type']==expected for s in info['streams']): raise RuntimeError('Invalid generated media')
    if expected=='audio':
        import soundfile as sf, numpy as np
        audio,_=sf.read(out)
        if not np.isfinite(audio).all() or np.max(np.abs(audio))<1e-5: raise RuntimeError('Silent or nonfinite model output')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--engine',required=True,choices=['ace-step','wan','flux-schnell','kokoro','whisper'])
    parser.add_argument('--output',required=True)
    parser.add_argument('--cache',required=True)
    parser.add_argument('--source')
    parser.add_argument('--verify',action='store_true')
    args=parser.parse_args();cache=Path(args.cache);cache.mkdir(parents=True,exist_ok=True)
    # A shared lock serializes model loads across the worker and installer.
    with (cache.parent/'inference.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        payload={'prompt':'An original gentle piano melody' if args.engine=='ace-step' else 'A calm lake at sunrise' if args.engine!='kokoro' else 'Welcome to Africa Creativity. This voice is generated by AI.','duration':5,'seed':42} if args.verify else json.load(sys.stdin)
        out=Path(args.output).resolve()
        if args.verify and args.engine=='whisper':
            sample=cache/'verify-speech.wav'
            subprocess.run(['espeak-ng','-w',str(sample),'Welcome to Africa Creativity'],check=True,timeout=30)
            args.source=str(sample)
        generate(args.engine,payload,out,cache,args.source)
        verify(out,args.engine)
        if args.verify and args.engine=='whisper' and not json.loads(out.read_text())['text'].strip(): raise RuntimeError('Speech verification produced no transcript')
    print(json.dumps({'engine':args.engine,'verified':True}))
if __name__=='__main__': main()
