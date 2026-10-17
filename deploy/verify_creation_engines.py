"""Render every selected local engine before activating it. Does not open the database."""
import argparse, json, sys, tempfile, wave, struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import engines

def verify(selected):
    if not isinstance(selected,list) or not selected or set(selected)-engines.CATALOG.keys():
        raise ValueError('Choose known local creation engines')
    reports=[]
    with tempfile.TemporaryDirectory() as directory:
        for engine in selected:
            path=Path(directory)/(engine+'.wav')
            score=engines.render(dict(engine=engine,duration=2,tempo=110,root=60,seed=7),path)
            with wave.open(str(path),'rb') as w:
                raw=w.readframes(w.getnframes());duration=w.getnframes()/w.getframerate()
                if not 1.9<=duration<=2.4 or w.getnchannels()!=1:raise RuntimeError('Invalid engine output')
            samples=struct.unpack('<'+'h'*(len(raw)//2),raw)
            if not samples or max(abs(x) for x in samples)<100:raise RuntimeError('Silent engine output')
            reports.append(dict(engine=engine,verified=True,duration=round(duration,3),notes=len(score['notes']),method='procedural; not AI'))
    return reports

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--engines',required=True)
    print(json.dumps(verify(json.loads(parser.parse_args().engines))))
