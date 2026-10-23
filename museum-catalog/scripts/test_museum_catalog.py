#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from typing import Any
spec=importlib.util.spec_from_file_location('museum_catalog', str(Path(__file__).with_name('museum_catalog.py')))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Tests(unittest.TestCase):
    def snapshot(self, title: str = '', caption: str = '') -> dict[str, Any]:
        return {'source':{'album_id':'album/1'},'photos':[{'id':'photo/1','title':title,'caption':caption,
            'album_membership':['album/1'],'capturedate':'2026-01-01T00:00:00.000Z','keywords':['keep'],
            'filename':'one.jpg','width':10,'height':20,'favorite':False}]}
    def manifest(self, **fields: str) -> dict[str, Any]:
        return {'works':{'w1':dict(identification='label',evidence={k:[{'label_photo_id':'label/1'}] for k in fields if k in ('title','artist','year','medium')},**fields)},'photos':[{'id':'photo/1','category':'artwork','work_id':'w1'}]}
    def test_title_only_and_unicode(self) -> None:
        plan=m.make_plan(self.snapshot(), self.manifest(title='L’été "bleu"\n\\ $()'))
        self.assertEqual(plan['changes'][0]['set'],{'title':'L’été "bleu"\n\\ $()'})
        self.assertEqual(json.loads(json.dumps(plan,ensure_ascii=False)),plan)
        m.validate_plan(plan)
    def test_no_guess_unknown_title(self) -> None:
        self.assertEqual(m.make_plan(self.snapshot(),self.manifest(artist='Artist'))['changes'][0]['set'],{'caption':'Artist: Artist'})
    def test_visual_qualified(self) -> None:
        x=self.manifest(title='Candidate',artist='Person');x['works']['w1']['identification']='visual'
        p=m.make_plan(self.snapshot(),x)['changes'][0]['set']
        self.assertEqual(p['title'],'Candidate');self.assertIn('Identification based on visual comparison.',p['caption'])
    def test_preserve_existing_and_allow_owned(self) -> None:
        snap=self.snapshot('My title','My caption')
        p=m.make_plan(snap,self.manifest(title='New'))['changes'][0]
        self.assertEqual(p['set'],{});self.assertEqual(p['preserved'],['title','caption'])
        p=m.make_plan(snap,self.manifest(title='New'),{'photo/1':{'title':'My title'}})['changes'][0]
        self.assertEqual(p['set'],{'title':'New'})
    def test_family_and_multi_work(self) -> None:
        x={'works':{},'photos':[{'id':'photo/1','category':'family','work_id':None}]}
        self.assertEqual(m.make_plan(self.snapshot('Mine'),x)['changes'][0]['set'],{})
        x['photos'][0].update(category='artwork',notes='Two works with verified label facts.')
        self.assertEqual(m.make_plan(self.snapshot(),x)['changes'][0]['set'],{'caption':'Two works with verified label facts.'})
    def test_guard_and_idempotence(self) -> None:
        snap=self.snapshot();plan=m.make_plan(snap,self.manifest(title='New'));live=copy.deepcopy(snap)
        def call(q: dict[str, Any]) -> Any:
            if q['op']=='inventory':return copy.deepcopy(live)
            out=[]
            for c in q['changes']:
                written=[];skipped=[]
                for k,v in c['set'].items():
                    if live['photos'][0][k]==c['expected'][k]:live['photos'][0][k]=v;written.append(k)
                    else:skipped.append(k)
                out.append({'id':c['id'],'written':written,'skipped':skipped})
            return out
        with tempfile.TemporaryDirectory() as d:
            r=m.apply_plan(plan,Path(d)/'log.json',Path(d)/'state.json',call)
            self.assertEqual(r['status'],'verified');self.assertEqual(live['photos'][0]['title'],'New')
            r=m.apply_plan(plan,Path(d)/'log2.json',None,call)
            self.assertEqual(r['writes'],[])
            live['photos'][0]['title']='User edit'
            r=m.apply_plan(plan,Path(d)/'log3.json',None,call)
            self.assertEqual(live['photos'][0]['title'],'User edit');self.assertEqual(len(r['skipped']),1)
    def test_interrupted_write_journal_recovery(self) -> None:
        snap=self.snapshot();plan=m.make_plan(snap,self.manifest(title='New',artist='Artist'))
        live=copy.deepcopy(snap)
        def call(q: dict[str, Any]) -> Any:
            if q['op']=='inventory':return copy.deepcopy(live)
            live['photos'][0]['title']='New'
            m.write(q['journal'],[{'id':'photo/1','written':['title'],'skipped':[]}])
            raise RuntimeError('Second field failed')
        with tempfile.TemporaryDirectory() as d:
            state=Path(d)/'state.json';log=Path(d)/'log.json'
            with self.assertRaises(RuntimeError):m.apply_plan(plan,log,state,call)
            self.assertEqual(m.read(state),{'photo/1':{'title':'New'}})
            self.assertEqual(m.read(log)['status'],'interrupted-or-failed')
            state.unlink()
            self.assertEqual(m.recover_journal(plan,log,state,call),{'status':'recovered','recovered':[{'id':'photo/1','field':'title'}],'skipped':[]})
            self.assertEqual(m.read(state),{'photo/1':{'title':'New'}})

    def test_setter_time_user_edit_surfaces_conflict_without_ownership(self) -> None:
        snap=self.snapshot();plan=m.make_plan(snap,self.manifest(title='New',artist='Artist'))
        live=copy.deepcopy(snap)
        def call(q: dict[str, Any]) -> Any:
            if q['op']=='inventory':return copy.deepcopy(live)
            # Edit arrives after Python preflight, immediately before JXA checks the setter.
            live['photos'][0]['title']='Fresh user title'
            live['photos'][0]['caption']='Artist: Artist'
            results=[{'id':'photo/1','written':['caption'],'skipped':['title']}]
            m.write(q['journal'],results)
            return results
        with tempfile.TemporaryDirectory() as d:
            state=Path(d)/'state.json';log=Path(d)/'log.json'
            result=m.apply_plan(plan,log,state,call)
            conflict=[{'id':'photo/1','field':'title'}]
            self.assertEqual(live['photos'][0]['title'],'Fresh user title')
            self.assertEqual(result['status'],'partial')
            self.assertEqual(result['skipped'],conflict)
            self.assertEqual(m.read(log)['skipped'],conflict)
            self.assertEqual(m.read(state),{'photo/1':{'caption':'Artist: Artist'}})
            state.unlink()
            recovered=m.recover_journal(plan,log,state,call)
            self.assertEqual(recovered['status'],'partial')
            self.assertEqual(recovered['skipped'],conflict)
            self.assertEqual(m.read(state),{'photo/1':{'caption':'Artist: Artist'}})

    def test_cli_apply_reports_conflicts(self) -> None:
        import contextlib
        import io
        from unittest.mock import patch
        plan=m.make_plan(self.snapshot(),self.manifest(title='New'))
        result={'status':'partial','skipped':[{'id':'photo/1','field':'title'}],'writes':[]}
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'plan.json';m.write(path,plan)
            output=io.StringIO()
            with patch.object(m,'apply_plan',return_value=result),contextlib.redirect_stdout(output):
                m.main(['apply','--plan',str(path),'--apply','--log',str(Path(d)/'log')])
            printed=json.loads(output.getvalue())
            self.assertEqual(printed['status'],'partial')
            self.assertEqual(printed['skipped'],result['skipped'])
            self.assertEqual(printed['written_fields'],0)

    def test_types_unknown_id_and_protected_guard(self) -> None:
        p=m.make_plan(self.snapshot(),self.manifest(title='New'));p['changes'][0]['set']['keywords']=[]
        with self.assertRaises(ValueError):m.validate_plan(p)
        p=m.make_plan(self.snapshot(),self.manifest(title='New'));p['changes'][0]['id']='wrong'
        with self.assertRaises(ValueError):m.validate_plan(p)
        p=m.make_plan(self.snapshot(),self.manifest(title='New'))
        live=self.snapshot();live['photos'][0]['keywords']=['changed']
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):m.apply_plan(p,Path(d)/'log',None,lambda _:live)

if __name__=='__main__':unittest.main()
