import ast, tempfile, unittest, sqlite3
from contextlib import closing
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
from flask import Flask, request, jsonify
import history_store as hs
import storage

class CaptureRecordsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.config={'history_db_path':str(self.root/'db.sqlite3'),'photo_dir':str(self.root/'photos')}
        (self.root/'photos').mkdir()
        self.name='2026-09-29_12-00-00.jpg'
        storage.photo_dir(self.config).joinpath(self.name).write_bytes(b'fixture')
        hs.record_sensor_sample(self.config,{},self.name)
        hs.record_sensor_sample(self.config,{})
        for backend in ['opencfu','mcount']:self.result(backend)
        app=Flask(__name__)
        ns=dict(vars(hs));ns.update(vars(storage));ns.update(app=app,request=request,jsonify=jsonify,config=self.config,datetime=datetime,
            require_auth=lambda f:f,external_storage=SimpleNamespace(photo_directories=lambda:[]),scheduler=SimpleNamespace(forget_photo=lambda n:None),
            request_filenames=lambda:request.get_json()['filenames'])
        tree=ast.parse(Path('app.py').read_text(encoding='utf-8'))
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'api_history','api_delete_photo','api_bulk_delete_photos'}]
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'app.py','exec'),ns)
        self.client=app.test_client()
    def result(self,backend):
        return hs.record_colony_result(self.config,filename=self.name,photo_timestamp='2026-09-29T12:00:00',backend=backend,status='ok',count=12,duration_seconds=1)
    def verify_deleted(self):
        self.assertFalse((self.root/'photos'/self.name).exists())
        self.assertEqual(hs.query_photo_history(self.config),[])
        self.result('mcount') # Simulate an in-flight job finishing after deletion.
        hs.record_sensor_sample(self.config,{},self.name)
        self.assertEqual(hs.query_photo_history(self.config),[])
        with closing(sqlite3.connect(self.config['history_db_path'])) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM sensor_samples').fetchone()[0],1)
    def test_single_delete_removes_linked_data_and_rejects_late_writes(self):
        self.assertEqual(self.client.delete('/api/photos/'+self.name).status_code,200);self.verify_deleted()
    def test_bulk_delete_handles_missing_photo_but_remaining_metadata(self):
        (self.root/'photos'/self.name).unlink()
        response=self.client.post('/api/photos/bulk-delete',json={'filenames':[self.name]})
        self.assertEqual(response.json['deleted'],[self.name]);self.verify_deleted()
    def test_union_includes_photo_without_history_and_history_without_photo(self):
        orphan='2026-09-28_10-00-00.jpg';(self.root/'photos'/orphan).write_bytes(b'fixture')
        (self.root/'photos'/self.name).unlink()
        rows=self.client.get('/api/history?mode=all&limit=all').json['records']
        self.assertEqual(len(rows),2)
        self.assertIn('photo',rows[0]);self.assertNotIn('photo',rows[1])
        rows=self.client.get('/api/history?mode=custom&limit=all&start=2026-09-29T00:00:00').json['records']
        self.assertEqual([r['filename'] for r in rows],[self.name])

if __name__=='__main__':unittest.main()

