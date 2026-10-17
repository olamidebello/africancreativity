"""Small procedural composition engines. These algorithms are not AI models."""
import os, math, random
import media
from database import Problem, number

CATALOG = {
    'arpeggio': 'Arpeggio sequencer · procedural · not AI',
    'chord-pad': 'Chord progression · procedural · not AI',
    'bassline': 'Bassline sequencer · procedural · not AI',
}
def enabled():
    return set(os.environ.get('LOCAL_CREATION_ENGINES', '').split(',')) & CATALOG.keys()

def catalog():
    return [dict(id=k, name=v, ready=k in enabled(), local=True) for k,v in CATALOG.items()]

def validate(p):
    engine=p.get('engine')
    if engine not in CATALOG: raise Problem('Unknown local composition engine')
    return dict(engine=engine, duration=number(p.get('duration',10),2,25),
                tempo=number(p.get('tempo',110),40,180), root=int(number(p.get('root',60),48,71)),
                seed=int(number(p.get('seed',0),0,1000000)))

def compose(payload):
    p=validate(payload); rng=random.Random(p['seed'])
    beats=p['duration']*p['tempo']/60
    notes=[]; progression=[0,5,9,7]
    def add(pitch,start,length,velocity):
        # The renderer adds a short release tail; never exceed its note bounds.
        if start<beats:
            notes.append(dict(pitch=pitch,start=start,duration=max(.125,min(length,beats-start)),velocity=velocity))
    engine=p['engine']
    if engine=='chord-pad':
        for bar in range(math.ceil(beats/4)):
            offset=progression[bar%4]
            for interval in (0,4,7):
                add(p['root']+offset+interval,bar*4,4,.35)
        waveform='sine'
    else:
        step=.5 if engine=='arpeggio' else 1
        for index in range(math.ceil(beats/step)):
            start=index*step; offset=progression[int(start//4)%4]
            if engine=='arpeggio':
                pitch=p['root']+offset+[0,4,7,12][(index+p['seed'])%4]
                add(pitch,start,.4,.5+rng.random()*.2)
            else:
                pitch=p['root']-12+offset+([0,0,7,0][index%4])
                add(pitch,start,.75,.6)
        waveform='triangle' if engine=='arpeggio' else 'sine'
    return dict(notes=notes,tempo=p['tempo'],waveform=waveform)

def render(payload,out):
    score=compose(payload); media.synth(score,out); return score
