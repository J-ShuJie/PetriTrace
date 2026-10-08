"""Paged research records, bounded chart samples and disk-backed exports."""
from __future__ import annotations
import csv
import json
import math
import os
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from history_store import init_db, _connect, _photo_index_sql, photo_history_by_filename, photo_timestamp_from_filename
from storage import list_photos, safe_photo_path

METRICS = ['sensor_a_temp_c','sensor_b_temp_c','sensor_a_humidity_percent','sensor_b_humidity_percent']

def capture_index(config, directories, start=None, end=None):
    init_db(config)
    sql,args = _photo_index_sql(start,end)
    with _connect(config) as conn:
        items={r['filename']:dict(r) for r in conn.execute(sql,args)}
    for photo in list_photos(config,limit=0,additional_dirs=directories):
        stamp=photo_timestamp_from_filename(photo['filename'],datetime.fromtimestamp(photo['mtime']).isoformat(timespec='seconds'))
        if (start and stamp<start) or (end and stamp>end):continue
        row=items.setdefault(photo['filename'],{'filename':photo['filename'],'timestamp':stamp})
        row['photo']=photo
    return sorted(items.values(),key=lambda r:(r['timestamp'],r['filename']))

def hydrate(config,index):
    meta=photo_history_by_filename(config,[r['filename'] for r in index])
    return [{**meta[r['filename']],**r} for r in index]

def record_page(config,index,page=1,size=25,focus=None):
    size=max(1,min(50,int(size)));pages=max(1,math.ceil(len(index)/size));page=max(1,min(int(page),pages))
    found = next((i for i, row in enumerate(reversed(index)) if row["filename"] == focus), None) if focus else None
    if found is not None: page = found // size + 1
    offset=(page-1)*size
    selected=list(reversed(index))[offset:offset+size]
    return {'records':hydrate(config,selected),'page':page,'pages':pages,'page_size':size,'total':len(index),'focus_found': found is not None}

def chart_samples(config,index,budget=1200):
    # Each bucket keeps its endpoints and min/max for all six displayed metrics.
    width=max(1,math.ceil(len(index)/max(1,budget//14)))
    selected={};bucket=[]
    def compact(rows):
        if not rows:return
        keep={0,len(rows)-1}
        for metric in METRICS+['opencfu','mcount']:
            values=[]
            for i,row in enumerate(rows):
                v=row.get(metric) if metric in METRICS else row.get('counts',{}).get(metric,{}).get('count')
                if isinstance(v,(int,float)) and math.isfinite(v):values.append((v,i))
            if values:keep.update([min(values)[1],max(values)[1]])
        for i in keep:
            row=dict(rows[i]);row.pop('photo',None)
            row['counts']={k:{'count':v.get('count'),'status':v.get('status')} for k,v in row.get('counts',{}).items()}
            selected[row['filename']]=row
    for offset in range(0,len(index),256):
        for row in hydrate(config,index[offset:offset+256]):
            bucket.append(row)
            if len(bucket)>=width:compact(bucket);bucket=[]
    compact(bucket)
    return sorted(selected.values(),key=lambda r:(r['timestamp'],r['filename']))

def export_selection(config,directories,data):
    scope=data.get('scope','current')
    if scope not in {'current','custom','all','selected'}:raise ValueError('Invalid export scope')
    start,end=(None,None) if scope in {'all','selected'} else (data.get('start') or None,data.get('end') or None)
    for value in (start,end):
        if value:datetime.fromisoformat(value)
    if start and end and start>end:raise ValueError('Start must precede end')
    if scope=='custom' and (not start or not end):raise ValueError('Choose both start and end')
    parts=list(dict.fromkeys(data.get('parts') or []))
    if not parts or any(p not in {'photos','counts','capture_sensors','environment'} for p in parts):raise ValueError('Choose export contents')
    index=capture_index(config,directories,start,end)
    if scope=='selected':
        names=set(data.get('filenames') or [])
        if not names:raise ValueError('No records selected')
        index=[r for r in index if r['filename'] in names]
        if 'environment' in parts:raise ValueError('Independent environment samples require a time range')
    return index,parts,start,end

def export_estimate(config,index,parts,start,end):
    photos=[r['photo'] for r in index if r.get('photo')] if 'photos' in parts else []
    environment=0
    if 'environment' in parts:
        where,args=environment_where(start,end)
        with _connect(config) as conn:environment=conn.execute('SELECT COUNT(*) FROM sensor_samples WHERE '+where,args).fetchone()[0]
    size=sum(p['size'] for p in photos)+(len(index)*(int('counts' in parts)+int('capture_sensors' in parts))+environment)*256
    return {'records':len(index),'photos':len(photos),'environment':environment,'estimated_bytes':size,'format':'csv' if len(parts)==1 and parts[0]!='photos' else 'zip'}

def environment_where(start,end):
    where="(photo_filename IS NULL OR photo_filename = '')";args=[]
    if start:where+=' AND timestamp >= ?';args.append(start)
    if end:where+=' AND timestamp <= ?';args.append(end)
    return where,args

def write_table(path,kind,config,index,start,end):
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream)
        if kind=='environment':
            columns=['timestamp',*METRICS];writer.writerow(columns)
            where,args=environment_where(start,end)
            with _connect(config) as conn:
                for row in conn.execute('SELECT '+','.join(columns)+' FROM sensor_samples WHERE '+where+' ORDER BY timestamp,id',args):writer.writerow(tuple(row))
            return
        columns=['filename','timestamp',*(METRICS if kind=='capture_sensors' else ['opencfu_count','opencfu_status','mcount_count','mcount_status'])]
        writer.writerow(columns)
        for offset in range(0,len(index),256):
            for row in hydrate(config,index[offset:offset+256]):
                values=[row['filename'],row['timestamp']]
                if kind=='capture_sensors':values.extend(row.get(k) for k in METRICS)
                else:
                    for backend in ('opencfu','mcount'):
                        result=row.get('counts',{}).get(backend,{})
                        values.extend([result.get('count'),result.get('status')])
                writer.writerow(values)

def build_export(config,directories,data):
    index,parts,start,end=export_selection(config,directories,data)
    temp=tempfile.TemporaryDirectory(prefix='pi-camera-export-')
    try:
        root=Path(temp.name);tables=[]
        for part in parts:
            if part!='photos':
                path=root/(part+'.csv');write_table(path,part,config,index,start,end);tables.append(path)
        if len(parts)==1 and parts[0]!='photos':return temp,tables[0],'text/csv'
        archive=root/'capture-export.zip';missing=[]
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for path in tables:z.write(path,path.name)
            if 'photos' in parts:
                for row in index:
                    path=safe_photo_path(config,row['filename'],directories)
                    if path.is_file():z.write(path,'photos/'+path.name,compress_type=zipfile.ZIP_STORED)
                    else:missing.append(row['filename'])
            z.writestr('manifest.json',json.dumps({'scope':data.get('scope'),'start':start,'end':end,'contents':parts,'records':len(index),'missing_photos':missing,'join_key':'filename','data':'Original records, not chart samples'},ensure_ascii=False,indent=2))
        return temp,archive,'application/zip'
    except Exception:
        temp.cleanup();raise
