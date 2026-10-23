#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Local-only Photos inventory, reviewed metadata plans, and guarded updates."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable

JsonObject = dict[str, Any]
OwnershipState = dict[str, dict[str, str]]
PhotosCall = Callable[[JsonObject], Any]

JXA = r'''
ObjC.import('Foundation');
function run(argv) {
 const q=JSON.parse(ObjC.unwrap($.NSString.stringWithContentsOfFileEncodingError(argv[0], $.NSUTF8StringEncoding, null)));
 const app=Application('Photos');
 function containers() {
   let folders=[],albums=[],seen={};
   function walk(c,parent) {
     c.folders().forEach(f=>{let id=f.id();if(seen[id]){if(parent)folders.find(x=>x.id===id).parent=parent;return;}seen[id]=true;
       folders.push({id:id,name:f.name(),parent:parent});walk(f,id);});
     c.albums().forEach(a=>{let id=a.id();if(seen[id]){if(parent)albums.find(x=>x.id===id).parent=parent;return;}seen[id]=true;
       albums.push({id:id,name:a.name(),parent:parent});});
   }
   // Resolve hierarchy from actual collections: Photos parent() is unreliable on some versions.
   walk(app,null);
   return {folders:folders,albums:albums,scope:'Photos scriptable user albums; shared albums are not exposed by this API'};
 }
 function inventory(source) {
   const cs=containers(), ids=new Set();
   if(source.album_id){if(!cs.albums.some(a=>a.id===source.album_id))throw Error('Unknown user album ID');ids.add(source.album_id);}
   else {
     if(!cs.folders.some(f=>f.id===source.folder_id))throw Error('Unknown folder ID');
     const fs=new Set([source.folder_id]);let change=true;
     while(change){change=false;cs.folders.forEach(f=>{if(fs.has(f.parent)&&!fs.has(f.id)){fs.add(f.id);change=true;}});}
     cs.albums.forEach(a=>{if(fs.has(a.parent))ids.add(a.id);});
   }
   const photos={},membership={};
   cs.albums.forEach(a=>{app.albums.byId(a.id).mediaItems.id().forEach(id=>{
     if(!membership[id])membership[id]=[];membership[id].push(a.id);
     if(ids.has(a.id)&&!photos[id])photos[id]=app.mediaItems.byId(id);
   });});
   let rows=Object.keys(photos).sort().map(id=>{const p=photos[id];return {
     id:id,filename:p.filename(),title:p.name()||'',caption:p.description()||'',keywords:p.keywords()||[],
     capturedate:p.date().toISOString(),width:p.width(),height:p.height(),favorite:p.favorite(),
     album_membership:membership[id].sort()};});
   return {version:1,source:source,albums:cs.albums.filter(a=>ids.has(a.id)),photos:rows,scope:cs.scope};
 }
 if(q.op==='sources')return JSON.stringify(containers());
 if(q.op==='inventory')return JSON.stringify(inventory(q.source));
 if(q.op==='export') {
   const p=app.mediaItems.byId(q.id);if(p.id()!==q.id)throw Error('Photo ID mismatch');
   app.export([p],{to:Path(q.directory),usingOriginals:false});return JSON.stringify({id:q.id});
 }
 if(q.op==='apply'){
   // Recheck each field immediately before its write. Python verifies membership and immutable fields again after.
   let results=[];
   function journal(){
     if(q.journal){let ok=$(JSON.stringify(results)).writeToFileAtomicallyEncodingError(q.journal,true,$.NSUTF8StringEncoding,null);if(!ok)throw Error('Journal write failed');}
   }
   q.changes.forEach(c=>{const p=app.mediaItems.byId(c.id);if(p.id()!==c.id)throw Error('Photo ID mismatch');
     let r={id:c.id,written:[],skipped:[]};results.push(r);
     Object.keys(c.set).forEach(k=>{const prop=k==='title'?'name':'description';
       if((p[prop]()||'')!==c.expected[k])r.skipped.push(k);
       else {p[prop]=c.set[k];if((p[prop]()||'')!==c.set[k])throw Error('Setter readback mismatch');r.written.push(k);}
       journal();
     });
   });return JSON.stringify(results);
 }
 throw Error('Unknown operation');
}
'''


def read(path: str | Path) -> Any:
    return json.loads(Path(path).read_text())


def write(path: str | Path, value: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def photos_call(request: JsonObject) -> Any:
    with tempfile.TemporaryDirectory(prefix='museum-catalog-') as tmp:
        script, data = Path(tmp)/'photos.js', Path(tmp)/'request.json'
        script.write_text(JXA)
        write(data, request)
        result = subprocess.run(['osascript', '-l', 'JavaScript', str(script), str(data)],
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)


def desired_metadata(item: JsonObject, works: JsonObject) -> dict[str, str]:
    category = item.get('category')
    if category not in {'family', 'artwork', 'architecture', 'label', 'review'}:
        raise ValueError('Invalid category')
    work_id = item.get('work_id')
    if work_id is not None and (not isinstance(work_id, str) or work_id not in works):
        raise ValueError('Unknown work_id')
    art = works[work_id] if work_id is not None else {}
    if not isinstance(art, dict):
        raise ValueError('work must be an object')
    for key in ('title', 'artist', 'year', 'medium', 'notes', 'identification'):
        if key in art and not isinstance(art[key], str):
            raise ValueError('work.' + key + ' must be text')
    if 'notes' in item and not isinstance(item['notes'], str):
        raise ValueError('photo.notes must be text')
    if category != 'artwork':
        return {'title': '', 'caption': ''}
    if work_id is None:
        return {'title': '', 'caption': item.get('notes', '').strip()}
    identification = art.get('identification', 'unverified')
    if identification not in {'label', 'visual', 'unverified'}:
        raise ValueError('Invalid identification')
    evidence = art.get('evidence', {})
    if not isinstance(evidence, dict):
        raise ValueError('work.evidence must be an object')
    if identification != 'unverified':
        for field in ('title', 'artist', 'year', 'medium'):
            if not art.get(field, '').strip():
                continue
            entries = evidence.get(field, [])
            if not isinstance(entries, list) or not entries:
                raise ValueError('Missing field evidence: ' + field)
            for entry in entries:
                if not isinstance(entry, dict) or not any(isinstance(entry.get(k), str) and entry[k] for k in ('label_photo_id', 'photo_id', 'url')):
                    raise ValueError('Evidence requires label_photo_id, photo_id, or primary-source url')
    # Evidence is reviewed locally; visual matches may verify a title without verifying an edition.
    title = art.get('title', '').strip() if identification != 'unverified' else ''
    lines = []
    if identification != 'unverified':
        for key in ('artist', 'year', 'medium'):
            value = art.get(key, '').strip()
            if value:
                lines.append(key.capitalize() + ': ' + value)
    if identification == 'visual':
        lines.append('Identification based on visual comparison.')
    if art.get('notes', '').strip():
        lines.append(art['notes'].strip())
    return {'title': title, 'caption': '\n'.join(lines)}


def make_plan(snapshot: JsonObject, manifest: JsonObject, state: OwnershipState | None = None) -> JsonObject:
    state = state or {}
    records = {p['id']: p for p in snapshot['photos']}
    works = manifest['works']
    if not isinstance(works, dict):
        raise ValueError('manifest.works must be an object')
    items = manifest['photos']
    if not isinstance(items, list):
        raise ValueError('manifest.photos must be an array')
    seen, changes = set(), []
    for item in items:
        pid = item['id']
        if not isinstance(pid, str) or pid not in records or pid in seen:
            raise ValueError('Unknown or duplicate manifest photo ID')
        seen.add(pid)
        before, desired = records[pid], desired_metadata(item, works)
        update, preserved = {}, []
        for field in ('title', 'caption'):
            value = before[field]
            if not isinstance(value, str):
                raise ValueError('Snapshot metadata must be text')
            owned = field in state.get(pid, {}) and state[pid][field] == value
            if value == desired[field]:
                continue
            if not value or owned:
                update[field] = desired[field]
            else:
                preserved.append(field)
        changes.append({'id': pid, 'expected': {k: before[k] for k in ('title', 'caption')},
                        'set': update, 'preserved': preserved})
    return {'version': 1, 'source': snapshot['source'], 'baseline': snapshot['photos'], 'changes': changes}


def validate_plan(plan: JsonObject) -> dict[str, JsonObject]:
    if plan.get('version') != 1 or not isinstance(plan.get('changes'), list):
        raise ValueError('Invalid plan version or changes')
    source = plan.get('source', {})
    if (set(source) not in ({'album_id'}, {'folder_id'}) or
            not all(isinstance(v, str) and v for v in source.values())):
        raise ValueError('Plan requires one explicit source ID')
    baseline = {p['id']: p for p in plan['baseline']}
    seen = set()
    for c in plan['changes']:
        pid = c['id']
        if not isinstance(pid, str) or pid not in baseline or pid in seen:
            raise ValueError('Invalid or duplicate plan ID')
        seen.add(pid)
        if not isinstance(c['set'], dict) or not set(c['set']) <= {'title', 'caption'}:
            raise ValueError('Only title and caption writes are permitted')
        if not isinstance(c['expected'], dict) or set(c['expected']) != {'title', 'caption'}:
            raise ValueError('Expected values required for both fields')
        if not all(isinstance(v, str) for v in list(c['set'].values())+list(c['expected'].values())):
            raise ValueError('Metadata fields must be text')
        if any(c['expected'][k] != baseline[pid][k] for k in ('title', 'caption')):
            raise ValueError('Expected values do not match baseline')
    return baseline


IMMUTABLE = ('album_membership', 'capturedate', 'keywords', 'filename', 'width', 'height', 'favorite')


def aggregate_skips(skipped: list[JsonObject], writes: list[JsonObject]) -> list[JsonObject]:
    """Include setter-time races in the same conflict list as preflight races."""
    pairs = {(entry['id'], entry['field']) for entry in skipped}
    pairs.update((entry['id'], field) for entry in writes for field in entry.get('skipped', []))
    return [{'id': pid, 'field': field} for pid, field in sorted(pairs)]


def apply_plan(plan: JsonObject, log_path: str | Path, state_path: str | Path | None = None,
               call: PhotosCall = photos_call) -> JsonObject:
    baseline = validate_plan(plan)
    before = call({'op': 'inventory', 'source': plan['source']})
    live = {p['id']: p for p in before['photos']}
    selected = [c['id'] for c in plan['changes']]
    for pid in selected:
        if pid not in live:
            raise ValueError('Photo left selected source: ' + pid)
        if any(live[pid][k] != baseline[pid][k] for k in IMMUTABLE):
            raise ValueError('Source or protected metadata changed: ' + pid)
    changes, skipped = [], []
    for c in plan['changes']:
        allowed = {k: v for k, v in c['set'].items() if live[c['id']][k] == c['expected'][k]}
        skipped.extend({'id': c['id'], 'field': k} for k in c['set'] if k not in allowed)
        if allowed:
            changes.append(dict(c, set=allowed))
    receipt = {'before': before, 'plan': plan, 'skipped': skipped, 'status': 'started'}
    write(log_path, receipt)  # Durable receipt before the first mutation.
    journal_path = str(Path(str(log_path)+'.writes.json').resolve())
    write(journal_path, [])
    try:
        receipt['writes'] = call({'op': 'apply', 'changes': changes, 'journal': journal_path}) if changes else []
        receipt['skipped'] = aggregate_skips(receipt['skipped'], receipt['writes'])
        after = call({'op': 'inventory', 'source': plan['source']})
        receipt['after'] = after
        end = {p['id']: p for p in after['photos']}
        errors = []
        for pid in selected:
            if pid not in end or any(end[pid][k] != live[pid][k] for k in IMMUTABLE):
                errors.append('Protected metadata or source membership changed: ' + pid)
        written = {(r['id'], k) for r in receipt['writes'] for k in r['written']}
        for c in changes:
            for k, value in c['set'].items():
                if (c['id'], k) in written and end.get(c['id'], {}).get(k) != value:
                    errors.append('Write readback mismatch: ' + c['id'] + '/' + k)
        receipt['status'] = ('partial' if receipt['skipped'] else 'verified') if not errors else 'verification-failed'
        receipt['errors'] = errors
        if not errors and state_path:
            state = read(state_path) if Path(state_path).exists() else {}
            for c in changes:
                for k, value in c['set'].items():
                    if (c['id'], k) in written:
                        state.setdefault(c['id'], {})[k] = value
            write(state_path, state)
        if errors:
            raise ValueError('; '.join(errors))
        return receipt
    except Exception as exc:
        receipt['error'] = str(exc)
        receipt['status'] = 'interrupted-or-failed'
        receipt['writes'] = read(journal_path)
        receipt['skipped'] = aggregate_skips(receipt['skipped'], receipt['writes'])
        # A later setter may fail after earlier setters succeeded. Recover ownership only
        # for journaled successful writes whose values still match a fresh readback.
        try:
            recovery = call({'op': 'inventory', 'source': plan['source']})
            receipt['recovery_readback'] = recovery
            if state_path:
                end = {p['id']: p for p in recovery['photos']}
                state = read(state_path) if Path(state_path).exists() else {}
                written = {(r['id'], k) for r in receipt['writes'] for k in r['written']}
                for c in changes:
                    for k, value in c['set'].items():
                        if (c['id'], k) in written and end.get(c['id'], {}).get(k) == value:
                            state.setdefault(c['id'], {})[k] = value
                write(state_path, state)
        except Exception as recovery_error:
            receipt['recovery_error'] = str(recovery_error)
        raise
    finally:
        write(log_path, receipt)


def recover_journal(plan: JsonObject, log_path: str | Path, state_path: str | Path,
                    call: PhotosCall = photos_call) -> JsonObject:
    """Recover confirmed ownership after a terminated process, before making another plan."""
    validate_plan(plan)
    journal = read(str(log_path)+'.writes.json')
    live = {p['id']: p for p in call({'op': 'inventory', 'source': plan['source']})['photos']}
    state = read(state_path) if Path(state_path).exists() else {}
    allowed = {c['id']: c['set'] for c in plan['changes']}
    recovered = []
    original_receipt = read(log_path) if Path(log_path).exists() else {}
    skipped = aggregate_skips(original_receipt.get('skipped', []), journal)
    for entry in journal:
        pid = entry['id']
        for field in entry['written']:
            if pid not in allowed or field not in allowed[pid]:
                raise ValueError('Journal does not match reviewed plan')
            value = allowed[pid][field]
            if live.get(pid, {}).get(field) == value:
                state.setdefault(pid, {})[field] = value
                recovered.append({'id': pid, 'field': field})
            else:
                skipped.append({'id': pid, 'field': field})
    write(state_path, state)
    return {'status': 'partial' if skipped else 'recovered', 'recovered': recovered,
            'skipped': aggregate_skips(skipped, [])}


def prepare_previews(snapshot: JsonObject, output: str | Path, renders: str | Path | None = None,
                     allow_export: bool = False, size: int = 1600) -> list[JsonObject]:
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    mapping = read(renders) if renders else {}
    rows = []
    for photo in snapshot['photos']:
        pid = photo['id']
        key = hashlib.sha256(pid.encode()).hexdigest()[:20]
        target = out/(key+'.jpg')
        source = Path(mapping[pid]).expanduser().resolve() if pid in mapping else None
        if source and not source.is_file():
            raise ValueError('Missing supplied current render: ' + str(source))
        if source is None and allow_export:
            export_dir = out/('render-'+key)
            export_dir.mkdir(exist_ok=True)
            if any(export_dir.iterdir()):
                raise ValueError('Export directory is nonempty; use a fresh preview directory')
            photos_call({'op': 'export', 'id': pid, 'directory': str(export_dir)})
            files = [p for p in export_dir.iterdir() if p.is_file()]
            if len(files) != 1:
                raise ValueError('Expected one Photos rendered export for '+pid)
            source = files[0]
        if source:
            if source == target.resolve():
                raise ValueError('Preview output must differ from input render')
            subprocess.run(['sips', '-s', 'format', 'jpeg', '-Z', str(size), str(source), '--out', str(target)],
                           check=True, capture_output=True)
        rows.append({'id': pid, 'preview': str(target) if source else None,
                     'status': 'prepared' if source else 'needs-current-render'})
    write(out/'previews.json', rows)
    return rows


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('sources'); p.add_argument('--out', required=True)
    p = sub.add_parser('inventory')
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--album-id'); group.add_argument('--folder-id')
    p.add_argument('--out', required=True)
    p = sub.add_parser('plan')
    p.add_argument('--snapshot', required=True); p.add_argument('--manifest', required=True)
    p.add_argument('--state'); p.add_argument('--out', required=True)
    p = sub.add_parser('apply', help='Preview reviewed plan; --apply explicitly enables writes')
    p.add_argument('--plan', required=True); p.add_argument('--apply', action='store_true')
    p.add_argument('--log'); p.add_argument('--state')
    p = sub.add_parser('recover', help='Recover journaled ownership after interrupted apply')
    p.add_argument('--plan', required=True); p.add_argument('--log', required=True); p.add_argument('--state', required=True)
    p = sub.add_parser('previews')
    p.add_argument('--snapshot', required=True); p.add_argument('--out', required=True)
    p.add_argument('--renders', help='JSON map photo ID to trusted local current-render path')
    p.add_argument('--allow-export', action='store_true', help='Export rendered edited JPEG copies for missing renders')
    p.add_argument('--size', type=int, default=1600)
    args = parser.parse_args(argv)
    if sys.platform != 'darwin':
        parser.error('Museum Catalog requires macOS with Apple Photos and Apple Vision.')
    if args.command == 'sources':
        write(args.out, photos_call({'op': 'sources'}))
    elif args.command == 'inventory':
        source = {'album_id': args.album_id} if args.album_id else {'folder_id': args.folder_id}
        result = photos_call({'op': 'inventory', 'source': source})
        result['created_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write(args.out, result)
    elif args.command == 'plan':
        write(args.out, make_plan(read(args.snapshot), read(args.manifest), read(args.state) if args.state else None))
    elif args.command == 'apply':
        plan = read(args.plan); validate_plan(plan)
        if args.apply:
            if not args.log:
                parser.error('--apply requires --log')
            result = apply_plan(plan, args.log, args.state)
            print(json.dumps({'status': result['status'], 'skipped': result['skipped'],
                              'written_fields': sum(len(r['written']) for r in result['writes']),
                              'log': str(args.log)}, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(plan['changes'], ensure_ascii=False, indent=2))
    elif args.command == 'recover':
        print(json.dumps(recover_journal(read(args.plan), args.log, args.state), ensure_ascii=False, indent=2))
    elif args.command == 'previews':
        if args.size < 1:
            parser.error('--size must be positive')
        prepare_previews(read(args.snapshot), args.out, args.renders, args.allow_export, args.size)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as exc:
        print('Error: ' + str(exc), file=sys.stderr)
        sys.exit(1)
