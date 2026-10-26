"""Verify the deployed HTML and JSON over public HTTPS from the Actions runner."""
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def main(base):
    if urllib.parse.urlparse(base).scheme != 'https':
        raise ValueError('Public HTTPS URL required')
    for attempt in range(30):
        try:
            for name in ('index.html', 'live-turnout.json','test/index.html','test/live-turnout.json'):
                url=base.rstrip('/')+'/'+name+'?deployment_check='+str(time.time_ns())
                request=urllib.request.Request(url, headers={'Cache-Control':'no-cache', 'User-Agent':'ElectionDashboard-DeploymentCheck'})
                with urllib.request.urlopen(request, timeout=20) as response:
                    actual=response.read(2_000_001)
                expected=(ROOT/'_site'/name).read_bytes()
                if actual != expected:
                    raise ValueError(f'{name}: public content does not match the deployed commit yet')
                if name.endswith('.json'):
                    feed=json.loads(actual.decode('utf-8-sig'))
                    print(f'Public data verified: {len(feed["records"])} records; source={feed["source"]}', flush=True)
                print(f'{name}: SHA256 {hashlib.sha256(actual).hexdigest()}', flush=True)
            # Contest page + snapshot: HTML must match package; JSON only needs to be valid public shape
            # (CI forecast sync may rewrite the file between package and this check).
            for name in ('forecast.html',):
                url=base.rstrip('/')+'/'+name+'?deployment_check='+str(time.time_ns())
                request=urllib.request.Request(url, headers={'Cache-Control':'no-cache', 'User-Agent':'ElectionDashboard-DeploymentCheck'})
                with urllib.request.urlopen(request, timeout=20) as response:
                    actual=response.read(2_000_001)
                expected=(ROOT/'_site'/name).read_bytes()
                if actual != expected:
                    raise ValueError(f'{name}: public content does not match the deployed commit yet')
                print(f'{name}: SHA256 {hashlib.sha256(actual).hexdigest()}', flush=True)
            fc_url=base.rstrip('/')+'/forecasts-public.json?deployment_check='+str(time.time_ns())
            fc_req=urllib.request.Request(fc_url, headers={'Cache-Control':'no-cache', 'User-Agent':'ElectionDashboard-DeploymentCheck'})
            with urllib.request.urlopen(fc_req, timeout=20) as response:
                fc_raw=response.read(2_000_001)
            fc=json.loads(fc_raw.decode('utf-8-sig'))
            if not isinstance(fc, dict) or 'forecasts' not in fc or not isinstance(fc['forecasts'], list):
                raise ValueError('forecasts-public.json: missing forecasts array')
            print(f'forecasts-public.json: {len(fc["forecasts"])} forecasts; status={fc.get("status")}', flush=True)
            print('Public HTML and JSON both match this deployment.', flush=True)
            return
        except (urllib.error.URLError, ValueError, TimeoutError) as error:
            if attempt == 29:
                raise
            print(f'Waiting for Pages propagation ({attempt+1}/30): {error}', flush=True)
            time.sleep(10)

if __name__ == '__main__':
    main(sys.argv[1])
