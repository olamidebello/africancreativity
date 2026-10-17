"""Exercise local add-ons and optionally load selected models before service activation."""
import argparse,json,sys,tempfile,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import media,addons

def verify(selected,load_models=False):
    reports=[]
    with tempfile.TemporaryDirectory() as d:
        source=Path(d)/'source.wav';master=Path(d)/'master.wav';arranged=Path(d)/'arranged.wav'
        media.synth({'notes':[{'pitch':60,'start':0,'duration':2,'velocity':.5}],'tempo':120},source)
        if 'audio-tools' in selected:
            addons.master(source,{'loudness':-16},master)
            addons.arrange([(source,{'trim':0,'duration':.5}),(source,{'trim':.2,'duration':.4})],arranged)
            metrics=addons.analyze(arranged)
            if not .8<metrics['duration_seconds']<1:raise RuntimeError('Section arrangement verification failed')
            reports.append({'module':'audio-tools','verified':'synth, mastering, arrangement and measurement'})
        if 'note-tools' in selected:reports.append({'module':'note-tools','verified':'bundled browser tools; DOM tests in CI'})
        if 'musicgen' in selected:
            import torch,scipy
            from transformers import AutoProcessor,MusicgenForConditionalGeneration
            models=os.environ.get('MUSICGEN_MODELS','musicgen-small').split(',')
            if not models or set(models)-{'musicgen-small','musicgen-medium'}:raise ValueError('Unsupported MusicGen model')
            for model_id in models:
                if load_models:
                    processor=AutoProcessor.from_pretrained('facebook/'+model_id)
                    model=MusicgenForConditionalGeneration.from_pretrained('facebook/'+model_id,use_safetensors=True)
                    with torch.no_grad():result=model.generate(**processor(text=['An original soft instrumental'],return_tensors='pt'),max_new_tokens=50,do_sample=True)
                    if result.numel()==0:raise RuntimeError('MusicGen produced no samples')
                    reports.append({'module':model_id,'verified':'weights loaded and short sample generated'})
                    del model,processor,result
                else:reports.append({'module':model_id,'verified':'imports only; weights and generation unverified'})
        if 'stems' in selected:
            from demucs.pretrained import get_model
            from demucs.apply import apply_model
            if load_models:
                import torch
                model=get_model('htdemucs');model.eval()
                audio=torch.zeros(1,model.audio_channels,model.samplerate)
                with torch.no_grad():result=apply_model(model,audio,device='cpu',shifts=0,split=False)
                if result.numel()==0:raise RuntimeError('Demucs produced no stems')
                reports.append({'module':'stems','verified':'weights loaded and synthetic sample separated'})
            else:reports.append({'module':'stems','verified':'imports only; weights and separation unverified'})
        if 'motion-video' in selected:reports.append({'module':'motion-video','verified':'adapter enabled; provider access and real render require live validation'})
    return reports

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--modules',required=True);ap.add_argument('--load-models',action='store_true');args=ap.parse_args()
    print(json.dumps(verify(json.loads(args.modules),args.load_models)))
