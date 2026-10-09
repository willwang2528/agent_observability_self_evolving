"""Recreate public benchmark caches at the pinned source/data versions. No model calls."""
from pathlib import Path
import json,hashlib,subprocess,sys,urllib.request,zipfile,os
ROOT=Path(__file__).resolve().parents[3];B=ROOT/'machine_work/benchmarks';C=ROOT/'.benchmark_cache'

def run(args,**kwargs):subprocess.run([str(a) for a in args],check=True,**kwargs)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def download(url,path,expected):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if sha(path)==expected:return
        raise ValueError('Existing cache checksum mismatch: '+str(path))
    partial=path.with_suffix(path.suffix+'.partial')
    urllib.request.urlretrieve(url,partial)
    if sha(partial)!=expected:raise ValueError('Download checksum mismatch: '+url)
    partial.rename(path)

def main():
    C.mkdir(exist_ok=True)
    for name in ('alfworld','webshop','tau_bench'):
        p=json.loads((B/name/'protocol.json').read_text());repo=C/name;up=p['upstream']
        if not (repo/'.git').exists():
            repo.mkdir(exist_ok=True);run(['git','init',repo]);run(['git','-C',repo,'remote','add','origin',up['official_repo']+'.git'])
            run(['git','-C',repo,'fetch','--depth','1','origin',up['commit']]);run(['git','-C',repo,'checkout','--detach',up['commit']])
        if subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()!=up['commit']:raise ValueError('Wrong upstream checkout')
        if subprocess.check_output(['git','-C',str(repo),'diff','--stat'],text=True).strip():raise ValueError('Modified upstream checkout')
    # Dependencies: flat snapshot of only the exercised runtime. No neural baseline training packages.
    python=C/'venv/bin/python';uv=os.environ.get('UV_BINARY','uv')
    if not python.exists():run([uv,'venv','--python','3.11',C/'venv'])
    run([uv,'pip','install','--python',python,'--no-deps','-r',B/'requirements.lock'])
    run([uv,'pip','install','--python',python,'--no-deps','-e',C/'alfworld'])
    for row in json.loads((B/'alfworld/data_provenance.json').read_text()):
        archive=C/row['url'].split('/')[-1];download(row['url'],archive,row['sha256'])
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if '/valid_unseen/' in name:z.extract(name,C/'alfworld_data')
    for row in json.loads((B/'webshop/data_provenance.json').read_text()):
        entry=row['mirrors'][0];download(entry['url'],C/'webshop/data'/row['file'],entry['sha256'])
    env=os.environ.copy();env['PYTHONPATH']=str(C/'webshop');env['ALFWORLD_DATA']=str(C/'alfworld_data')
    if sys.platform=='darwin' and 'JAVA_HOME' not in env:
        env['JAVA_HOME']=subprocess.check_output(['/usr/libexec/java_home'],text=True).strip()
    search=C/'webshop/search_engine'
    for name in ('resources','resources_100','resources_1k','resources_100k'):(search/name).mkdir(exist_ok=True)
    run([python,'convert_product_file_format.py'],cwd=search,env=env)
    index=search/'indexes_1k'
    if not index.exists():
        run([python,'-m','pyserini.index.lucene','--collection','JsonCollection','--input',search/'resources_1k','--index',index,'--generator','DefaultLuceneDocumentGenerator','--threads','1','--storePositions','--storeDocvectors','--storeRaw'],cwd=ROOT,env=env)
    code="from pyserini.search.lucene import LuceneSearcher; s=LuceneSearcher("+repr(str(index))+"); assert s.num_docs==1000; print('WebShop Lucene docs:',s.num_docs)"
    run([python,'-c',code],env=env)
    print('Pinned environments prepared. This command makes no model calls.')
if __name__=='__main__':main()
