"""Daily expiry of cached YouTube API data and tokens for inactive connections."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import database as db,youtube_integration as yt
with db.connect() as c:
    yt.cleanup(c)
    for a in c.execute('SELECT a.user_id FROM youtube_accounts a LEFT JOIN users u ON u.id=a.user_id LEFT JOIN tenants t ON t.id=a.tenant_id WHERE u.id IS NULL OR u.active=0 OR u.role=\'super_admin\' OR t.status!=\'active\'').fetchall():
        yt.token_path(a['user_id']).unlink(missing_ok=True)
        c.execute('DELETE FROM youtube_accounts WHERE user_id=?',(a['user_id'],))
        c.execute('DELETE FROM youtube_imports WHERE user_id=?',(a['user_id'],))
