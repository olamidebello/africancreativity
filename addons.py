"""Bundled audio add-ons: real processing, never fabricated provider output."""
import math,array,shutil
import media
from database import Problem,number

def status():
    ready=bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))
    return [{'id':'audio-tools','installed':True,'ready':ready,'features':['section arrangement','loudness mastering','audio measurement']},
            {'id':'note-tools','installed':True,'ready':True,'features':['quantize','chord expansion','arpeggiator']}]

def master(src,p,out):
    loudness=number(p.get('loudness',-16),-24,-9)
    media.ff(['-protocol_whitelist','file,pipe','-i',str(src),'-vn','-af',f'loudnorm=I={loudness}:TP=-1.5:LRA=11','-t','180','-ar','44100','-ac','2','-c:a','pcm_s16le',str(out)])

def arrange(clips,out):
    if not 1<=len(clips)<=12:raise Problem('Select 1–12 audio sections')
    args=[];filters=[];names=[];total=0
    for i,(src,p) in enumerate(clips):
        start=number(p.get('trim',0),0,600);duration=number(p.get('duration',5),.05,120);total+=duration
        if total>180:raise Problem('Arrangement must be at most 180 seconds')
        _,available=media.probe(src)
        if start+duration>available+.01:raise Problem('Section extends beyond its source recording')
        args+=['-protocol_whitelist','file,pipe','-i',str(src)]
        filters.append(f'[{i}:a]atrim=start={start}:duration={duration},asetpts=PTS-STARTPTS,aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[s{i}]');names.append(f'[s{i}]')
    filters.append(''.join(names)+f'concat=n={len(clips)}:v=0:a=1[out]')
    media.ff([*args,'-filter_complex_threads','1','-filter_complex',';'.join(filters),'-map','[out]','-c:a','pcm_s16le',str(out)])

def analyze(src):
    _,duration=media.probe(src)
    raw=media.ff(['-protocol_whitelist','file,pipe','-i',str(src),'-vn','-t','180','-ac','1','-ar','8000','-f','s16le','pipe:1'])
    values=array.array('h');values.frombytes(raw)
    if not values:raise Problem('Audio contains no samples')
    peak=max(abs(v) for v in values)/32768;rms=math.sqrt(sum((v/32768)**2 for v in values)/len(values))
    # Energy onset autocorrelation is an estimate, not a semantic music/emotion model.
    hop=160;energy=[math.sqrt(sum((v/32768)**2 for v in values[i:i+hop])/max(1,len(values[i:i+hop]))) for i in range(0,len(values),hop)]
    onset=[max(0,b-a) for a,b in zip(energy,energy[1:])];best=(0,None)
    for lag in range(15,min(76,len(onset)//2)):
        score=sum(onset[i]*onset[i-lag] for i in range(lag,len(onset)))
        if score>best[0]:best=(score,lag)
    bpm=round(3000/best[1],1) if best[1] and best[0]>1e-6 else None
    return dict(duration_seconds=round(duration,3),measured_seconds=round(len(values)/8000,3),peak_dbfs=round(20*math.log10(max(peak,1e-9)),2),rms_dbfs=round(20*math.log10(max(rms,1e-9)),2),clipped_samples=sum(abs(v)>=32760 for v in values),estimated_bpm=bpm,method='Mono energy-onset estimate; verify tempo manually. No lyrics or emotion detection.')
