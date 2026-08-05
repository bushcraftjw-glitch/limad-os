from __future__ import annotations
import json,sqlite3,tempfile,uuid,zipfile,shutil
from pathlib import Path
from ..database import DB,Database
from ..utils import utc_now,safe_extract,safe_zip_members

def list_playlists(database:Database=DB)->list[dict]:
    rows=database.rows('SELECT * FROM local_playlists ORDER BY updated_at DESC')
    for row in rows:
        row['items']=database.rows('SELECT * FROM local_playlist_items WHERE playlist_id=? ORDER BY position',(row['id'],))
    return rows

def create_playlist(title:str,description:str='',database:Database=DB)->dict:
    pid=uuid.uuid4().hex;now=utc_now();database.execute('INSERT INTO local_playlists(id,title,description,created_at,updated_at) VALUES(?,?,?,?,?)',(pid,title.strip() or 'Neue Playlist',description.strip(),now,now));return list_playlists(database)[0]

def add_item(playlist_id:str,label:str,publication_id:str='',file_path:str='',media_url:str='',mime_type:str='',thumbnail_path:str='',start_seconds:float=0,end_seconds:float|None=None,source:dict|None=None,database:Database=DB)->dict:
    pos=int(database.scalar('SELECT COALESCE(MAX(position),-1)+1 FROM local_playlist_items WHERE playlist_id=?',(playlist_id,)) or 0);iid=uuid.uuid4().hex
    database.execute('''INSERT INTO local_playlist_items(id,playlist_id,position,label,publication_id,file_path,media_url,mime_type,thumbnail_path,start_seconds,end_seconds,source_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(iid,playlist_id,pos,label or file_path or 'Medieninhalt',publication_id,file_path,media_url,mime_type,thumbnail_path,float(start_seconds or 0),end_seconds,json.dumps(source or {},ensure_ascii=False),utc_now()))
    database.execute('UPDATE local_playlists SET updated_at=? WHERE id=?',(utc_now(),playlist_id));return database.rows('SELECT * FROM local_playlist_items WHERE id=?',(iid,))[0]

def delete_playlist(playlist_id:str,database:Database=DB): database.execute('DELETE FROM local_playlists WHERE id=?',(playlist_id,))

def reorder_items(playlist_id:str,item_ids:list[str],database:Database=DB):
    with database.transaction() as con:
        for pos,iid in enumerate(item_ids): con.execute('UPDATE local_playlist_items SET position=? WHERE id=? AND playlist_id=?',(pos,iid,playlist_id))
        con.execute('UPDATE local_playlists SET updated_at=? WHERE id=?',(utc_now(),playlist_id))
    return [p for p in list_playlists(database) if p['id']==playlist_id][0]

def _table(con,name): return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone() is not None

def import_jwlplaylist(path:Path,database:Database=DB)->dict:
    path=Path(path)
    with tempfile.TemporaryDirectory(prefix='limad-playlist-') as tmp:
        root=Path(tmp)
        with zipfile.ZipFile(path) as z: safe_extract(z,root,safe_zip_members(z,max_files=10000,max_size=3_000_000_000))
        dbs=list(root.rglob('*.db'))
        if not dbs: raise ValueError('Playlist-Datenbank fehlt.')
        con=sqlite3.connect(dbs[0]);con.row_factory=sqlite3.Row
        try:
            title=path.stem
            manifest=root/'manifest.json'
            if manifest.is_file():
                data=json.loads(manifest.read_text(encoding='utf-8-sig'));title=data.get('name') or data.get('title') or title
            playlist=create_playlist(title,database=database);count=0
            if _table(con,'PlaylistItem'):
                for row in con.execute('SELECT * FROM PlaylistItem ORDER BY PlaylistItemId'):
                    r=dict(row);label=r.get('Label') or f'Element {count+1}';thumb=r.get('ThumbnailFilePath') or ''
                    add_item(playlist['id'],label,thumbnail_path=thumb,start_seconds=float(r.get('StartTrimOffsetTicks') or 0)/10_000_000,end_seconds=(float(r.get('EndTrimOffsetTicks'))/10_000_000 if r.get('EndTrimOffsetTicks') else None),source=r,database=database);count+=1
            return {'playlist_id':playlist['id'],'title':title,'items':count}
        finally: con.close()

def export_jwlplaylist(playlist_id:str,target:Path,database:Database=DB)->dict:
    playlists=[p for p in list_playlists(database) if p['id']==playlist_id]
    if not playlists: raise ValueError('Playlist fehlt.')
    p=playlists[0]
    with tempfile.TemporaryDirectory(prefix='limad-playlist-export-') as tmp:
        root=Path(tmp);db=root/'userData.db';con=sqlite3.connect(db)
        con.executescript('''CREATE TABLE PlaylistItem(PlaylistItemId INTEGER PRIMARY KEY,Label TEXT,StartTrimOffsetTicks INTEGER,EndTrimOffsetTicks INTEGER,Accuracy INTEGER,EndAction INTEGER,ThumbnailFilePath TEXT);CREATE TABLE PlaylistItemLocationMap(PlaylistItemId INTEGER,LocationId INTEGER,MajorMultimediaType INTEGER,BaseDurationTicks INTEGER);CREATE TABLE PlaylistItemMarker(PlaylistItemMarkerId INTEGER PRIMARY KEY,PlaylistItemId INTEGER,Label TEXT,StartTimeTicks INTEGER,DurationTicks INTEGER,EndTransitionDurationTicks INTEGER);''')
        for idx,item in enumerate(p['items'],1): con.execute('INSERT INTO PlaylistItem VALUES(?,?,?,?,?,?,?)',(idx,item['label'],int(float(item.get('start_seconds') or 0)*10_000_000),int(float(item['end_seconds'])*10_000_000) if item.get('end_seconds') is not None else None,0,0,item.get('thumbnail_path') or ''))
        con.commit();con.close();(root/'manifest.json').write_text(json.dumps({'name':p['title'],'version':1,'created':utc_now()},ensure_ascii=False,indent=2),encoding='utf-8')
        target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
            z.write(db,'userData.db');z.write(root/'manifest.json','manifest.json')
    return {'path':str(target),'items':len(p['items'])}
