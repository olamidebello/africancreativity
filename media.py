"""Bounded local audio/video operations. All paths come from authorized database assets."""
import json,subprocess,math,wave,struct,tempfile,uuid,shutil,os
from pathlib import Path
import database as db
from database import Problem,number

def run(args,timeout=180):
    try:r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    except subprocess.TimeoutExpired:raise Problem('Media operation timed out',422)
    if r.returncode:raise Problem('Media could not be processed. Check the source format and selected settings.',422)
    return r.stdout

def ff(args,timeout=180):return run(['ffmpeg','-v','error','-nostdin','-y','-threads','1',*args],timeout)
def probe(path):
    raw=run(['ffprobe','-v','error','-protocol_whitelist','file,pipe','-format_whitelist','wav,mp3,ogg,mov,matroska,webm,png_pipe,jpeg_pipe,image2','-show_format','-show_streams','-of','json',str(path)],20)
    try:d=json.loads(raw)
    except ValueError:raise Problem('Invalid media')
    streams=d.get('streams',[])
    if not streams:raise Problem('No media streams found')
    duration=number(d.get('format',{}).get('duration',0),0,600)
    return d, duration

def newfile(ext):return db.DATA/'media'/(uuid.uuid4().hex+'.'+ext)
def diskpath(a):
    p=(db.DATA/'media'/a['path']).resolve()
    if p.parent!=(db.DATA/'media').resolve() or not p.is_file():raise Problem('Media file not found',404)
    return p

def synth(payload,out):
    notes=payload.get('notes',[])
    if not isinstance(notes,list) or not 1<=len(notes)<=256:raise Problem('Add 1–256 piano-roll notes')
    tempo=number(payload.get('tempo',110),30,240);rate=22050
    validated=[]
    for n in notes:
        pitch=number(n.get('pitch'),24,96);start=number(n.get('start'),0,128)*60/tempo;duration=number(n.get('duration'),.125,16)*60/tempo;velocity=number(n.get('velocity',.7),0,1)
        validated.append((pitch,start,duration,velocity))
    length=min(90,max(s+d for _,s,d,_ in validated)+.2);buf=[0.0]*int(length*rate)
    waveform=payload.get('waveform','sine')
    if waveform not in ('sine','triangle','sawtooth','square'):raise Problem('Invalid oscillator')
    for pitch,start,duration,velocity in validated:
        freq=440*2**((pitch-69)/12)
        for i in range(int(start*rate),min(len(buf),int((start+duration)*rate))):
            t=i/rate-start;phase=t*freq%1
            x=math.sin(2*math.pi*phase) if waveform=='sine' else 1-4*abs(phase-.5) if waveform=='triangle' else 2*phase-1 if waveform=='sawtooth' else (1 if phase<.5 else -1)
            envelope=min(1,t/.015,max(0,(duration-t)/.06))
            buf[i]+=x*velocity*envelope*.25
    peak=max(1,max(abs(x) for x in buf));samples=struct.pack('<'+'h'*len(buf),*(int(x/peak*30000) for x in buf))
    with wave.open(str(out),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(samples)

def edit(src,p,out):
    _,duration=probe(src);start=number(p.get('start',0),0,duration);end=number(p.get('end',duration),start+.02,duration)
    speed=number(p.get('speed',1),.5,2);pitch=number(p.get('pitch',0),-12,12);vol=number(p.get('volume',1),0,2)
    filters=['atrim=start='+str(start)+':end='+str(end),'asetpts=PTS-STARTPTS','aresample=44100']
    if p.get('reverse'):filters+=['areverse']
    ratio=2**(pitch/12);filters+=['asetrate='+str(44100*ratio),'aresample=44100']
    # Keep pitch independent of speed using bounded chained tempo filters.
    t=speed/ratio
    while t<.5:filters+=['atempo=0.5'];t/=.5
    while t>2:filters+=['atempo=2'];t/=2
    filters+=['atempo='+str(t),'volume='+str(vol)]
    length=(end-start)/speed
    fadein=number(p.get('fade_in',0),0,min(10,length));fadeout=number(p.get('fade_out',0),0,min(10,length))
    if fadein:filters+=['afade=t=in:d='+str(fadein)]
    if fadeout:filters+=['afade=t=out:st='+str(max(0,length-fadeout))+':d='+str(fadeout)]
    effects=p.get('effects',[])
    if not isinstance(effects,list) or len(effects)>8:raise Problem('Maximum eight effects')
    for effect in effects:
        name=effect.get('type');amount=number(effect.get('amount',.5),0,1)
        if effect.get('bypass'):continue
        if name=='compressor':filters+=['acompressor=threshold=0.2:ratio='+str(1+amount*7)]
        elif name=='eq':filters+=['equalizer=f=1000:t=q:w=1:g='+str((amount-.5)*24)]
        elif name=='delay':filters+=['aecho=0.8:0.8:250:'+str(amount*.7)]
        elif name=='reverb':filters+=['aecho=0.8:0.8:40|90:0.25|'+str(amount*.4)]
        elif name=='distortion':filters+=['asoftclip=type=tanh:threshold='+str(1-.8*amount)]
        elif name=='gate':filters+=['agate=threshold='+str(.001+amount*.1)]
        else:raise Problem('Unsupported effect')
    ff(['-protocol_whitelist','file,pipe','-i',str(src),'-vn','-af',','.join(filters),'-t','180','-ac','2','-c:a','pcm_s16le',str(out)])

def mix(clips,out,tempo=120):
    if not 1<=len(clips)<=12:raise Problem('Add 1–12 clips')
    args=[];filters=[];names=[]
    for i,(src,p) in enumerate(clips):
        args+=['-protocol_whitelist','file,pipe','-i',str(src)]
        start=number(p.get('offset',0),0,120);trim=number(p.get('trim',0),0,600);duration=number(p.get('duration',10),.05,120)
        gain=number(p.get('volume',1),0,2);pan=number(p.get('pan',0),-1,1)
        if p.get('muted'):gain=0
        left=min(1,1-pan);right=min(1,1+pan)
        filters.append(f'[{i}:a]atrim=start={trim}:duration={duration},asetpts=PTS-STARTPTS,aformat=channel_layouts=stereo,volume={gain},pan=stereo|c0={left}*c0|c1={right}*c1,adelay={int(start*1000)}|{int(start*1000)}[a{i}]');names.append(f'[a{i}]')
    filters.append(''.join(names)+f'amix=inputs={len(clips)}:duration=longest:normalize=1[out]')
    ff([*args,'-filter_complex_threads','1','-filter_complex',';'.join(filters),'-map','[out]','-t','180','-c:a','pcm_s16le',str(out)])

def video(audio,scenes,p,out):
    if not 1<=len(scenes)<=12:raise Problem('Add 1–12 scenes')
    ratio=p.get('aspect','16:9')
    if ratio not in ('16:9','9:16','1:1'):raise Problem('Invalid aspect ratio')
    w,h={'16:9':(960,540),'9:16':(540,960),'1:1':(720,720)}[ratio]
    with tempfile.TemporaryDirectory() as d:
        segments=[];total=0
        for i,(image,s) in enumerate(scenes):
            dur=number(s.get('duration',5),2,15);total+=dur
            if total>120:raise Problem('Video must be at most 120 seconds')
            segment=Path(d)/f'{i}.mp4';caption=Path(d)/f'{i}.txt';caption.write_text(str(s.get('subtitle',''))[:250])
            vf=f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1'
            font=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
            if caption.read_text() and font.exists():vf+=f",drawtext=fontfile={font}:textfile={caption}:expansion=none:fontcolor=white:fontsize=26:box=1:boxcolor=black@0.6:boxborderw=12:x=(w-text_w)/2:y=h-80"
            inp=(['-stream_loop','-1','-i',str(image)] if s.get('resource_kind')=='video' else ['-loop','1','-i',str(image)]) if image else ['-f','lavfi','-i',f'color=c=0x171c34:s={w}x{h}:r=24']
            ff([*inp,'-vf',vf,'-t',str(dur),'-an','-r','24','-c:v','libx264','-pix_fmt','yuv420p','-preset','ultrafast',str(segment)])
            segments.append(segment)
        listing=Path(d)/'segments.txt';listing.write_text(''.join(f"file '{s}'\n" for s in segments))
        args=['-f','concat','-safe','0','-i',str(listing)]
        if audio:args+=['-protocol_whitelist','file,pipe','-i',str(audio),'-map','0:v','-map','1:a','-af','apad','-c:a','aac']
        ff([*args,'-t',str(total),'-c:v','copy','-movflags','+faststart',str(out)])

def waveform(src):
    raw=ff(['-protocol_whitelist','file,pipe','-i',str(src),'-vn','-ac','1','-ar','8000','-t','180','-f','s16le','pipe:1'])
    import array
    samples=array.array('h');samples.frombytes(raw);step=max(1,len(samples)//180)
    return [round(max(abs(x) for x in samples[i:i+step])/32768,3) for i in range(0,len(samples),step)][:180]
