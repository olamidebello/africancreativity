fetch('/downloads/africa-creativity.apk.sha256',{credentials:'omit',cache:'no-store'})
 .then(response=>{if(!response.ok)throw Error('pending');return response.text()})
 .then(()=>{document.getElementById('download-status').textContent='Android download is ready.'})
 .catch(()=>{const link=document.getElementById('app-download');link.removeAttribute('href');link.removeAttribute('download');link.setAttribute('aria-disabled','true');link.textContent='Android package pending deployment';document.getElementById('download-status').textContent='Use the website until the Android package is deployed.'});
