import unittest,tempfile,zipfile,csv,sqlite3,json
from pathlib import Path
from contextlib import closing
from research_records import *
from history_store import record_sensor_sample,record_colony_result

class ResearchRecordsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.config={'photo_dir':str(self.root/'photos'),'history_db_path':str(self.root/'history.db')};(self.root/'photos').mkdir()
  for i in range(3):
   name=f'2026-09-29_12-00-0{i}.jpg';(self.root/'photos'/name).write_bytes(b'photo')
   record_sensor_sample(self.config,{},name)
   record_colony_result(self.config,filename=name,photo_timestamp=f'2026-09-29T12:00:0{i}',backend='opencfu',status='ok',count=i,duration_seconds=1)
  record_sensor_sample(self.config,{})
 def test_page_is_bounded_and_newest_first(self):
  index=capture_index(self.config,[]);page=record_page(self.config,index,1,2)
  self.assertEqual(len(page['records']),2);self.assertEqual(page['pages'],2);self.assertTrue(page['records'][0]['filename'].endswith('02.jpg'))
 def test_focus_locates_the_correct_page_without_changing_page_size(self):
  index=capture_index(self.config,[])
  result=record_page(self.config,index,1,2,focus=index[0]['filename'])
  self.assertEqual(result['page'],2);self.assertEqual(result['page_size'],2);self.assertTrue(result['focus_found'])
  self.assertEqual(result['records'][0]['filename'],index[0]['filename'])
  self.assertFalse(record_page(self.config,index,1,2,focus='missing.jpg')['focus_found'])
 def test_export_zip_contains_original_files_and_both_data_categories(self):
  tmp,path,kind=build_export(self.config,[],{'scope':'all','parts':['photos','counts','capture_sensors','environment']})
  try:
   self.assertEqual(kind,'application/zip')
   with zipfile.ZipFile(path) as z:
    self.assertEqual(len([n for n in z.namelist() if n.startswith('photos/')]),3)
    self.assertEqual(len(list(csv.reader(z.read('counts.csv').decode('utf-8-sig').splitlines()))),4)
    self.assertEqual(len(list(csv.reader(z.read('environment.csv').decode('utf-8-sig').splitlines()))),2)
    self.assertEqual(json.loads(z.read('manifest.json'))['records'],3)
  finally:tmp.cleanup()
 def test_selected_csv_and_custom_scope(self):
  name='2026-09-29_12-00-01.jpg'
  tmp,path,kind=build_export(self.config,[],{'scope':'selected','filenames':[name],'parts':['counts']})
  try:
   rows=list(csv.reader(path.read_text(encoding='utf-8-sig').splitlines()));self.assertEqual(len(rows),2);self.assertEqual(rows[1][0],name)
  finally:tmp.cleanup()
  index,*_=export_selection(self.config,[],{'scope':'custom','start':'2026-09-29T12:00:01','end':'2026-09-29T12:00:01','parts':['photos']});self.assertEqual(len(index),1)
  with self.assertRaises(ValueError):export_selection(self.config,[],{'scope':'selected','filenames':[name],'parts':['environment']})
 def test_chart_limit_preserves_spikes_and_export_is_not_sampled(self):
  with closing(sqlite3.connect(self.config['history_db_path'])) as conn:
   conn.executemany('INSERT INTO colony_results(filename,photo_timestamp,backend,status,colony_count,analyzed_at,details_json) VALUES (?,?,?,?,?,?,?)',[(f'fixture-{i}.jpg',f'2025-01-01T00:{i//60:02}:{i%60:02}','mcount','ok',9999 if i==1555 else 1,'2026-01-01','{}') for i in range(3000)]);conn.commit()
  index=capture_index(self.config,[]);points=chart_samples(self.config,index)
  self.assertLessEqual(len(points),1200);self.assertTrue(any(r.get('counts',{}).get('mcount',{}).get('count')==9999 for r in points));self.assertEqual(record_page(self.config,index)['total'],3003)
  tmp,path,_=build_export(self.config,[],{'scope':'all','parts':['counts']})
  try:self.assertEqual(len(list(csv.reader(path.read_text(encoding='utf-8-sig').splitlines()))),3004)
  finally:tmp.cleanup()
 def test_form_export_stream_and_preview_share_selection(self):
  import ast,threading
  from types import SimpleNamespace
  from flask import Flask,request,jsonify,Response
  app=Flask(__name__)
  ns=dict(globals());ns.update(app=app,request=request,jsonify=jsonify,Response=Response,config=self.config,require_auth=lambda f:f,external_storage=SimpleNamespace(photo_directories=lambda:[]),_export_lock=threading.Lock())
  tree=ast.parse(Path('app.py').read_text(encoding='utf-8'))
  nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'api_export','api_export_preview','research_range','api_records','api_charts'}]
  exec(compile(ast.Module(body=nodes,type_ignores=[]),'app.py','exec'),ns)
  client=app.test_client();payload={'scope':'all','parts':['counts']}
  self.assertEqual(client.post('/api/export/preview',json=payload).json['records'],3)
  response=client.post('/api/export',data={'payload':json.dumps(payload)})
  self.assertEqual(response.status_code,200);self.assertIn('counts.csv',response.headers['Content-Disposition'])
  self.assertEqual(len(list(csv.reader(response.data.decode('utf-8-sig').splitlines()))),4);response.close()
  self.assertEqual(len(client.get('/api/records?mode=all&page_size=2').json['records']),2)
  self.assertEqual(client.get('/api/charts?mode=all').json['summary']['total'],3)
  self.assertEqual(client.post('/api/export',json={'scope':'custom','start':'invalid','end':'invalid','parts':['counts']}).status_code,400)

if __name__=='__main__':unittest.main()
