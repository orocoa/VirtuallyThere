import json
from .store import locked, revision, verify, read

CAMERAS = {
 'elevations': 'THREE separate panels of the SAME object: FRONT (camera at negative Y), RIGHT (camera at positive X), BACK (camera at positive Y). Orthographic, object upright Z, identical scale and baseline.',
 'volume': 'THREE separate panels of the SAME object: TOP (positive Z looking down), BOTTOM (negative Z looking up), FRONT-RIGHT THREE-QUARTER (positive X, negative Y, positive Z). Top and bottom orthographic; three-quarter weak perspective.'
}

def prompts(job):
    with locked(job) as (job, data):
        folder, r = revision(job, data)
        brief = read(verify(r['brief'], job))
        common = ('Use case: product-mockup. Asset: modeling reference, not a finished photograph. '
          'One coherent abstract monochrome small sculpture, exact same identity across all views. '
          f'Do not create alternate designs in the panels. Neutral matte {brief.get("color","white")} material and contrasting neutral background; soft studio light. '
          'No furniture, decorative plinth, props, floating parts or metallic/glass illusions. Whole object fully visible, ample margins, no overlap. '
          'Camera labels outside the object; no extra text on the object. '
          'Preserve silhouette, count of volumes, connections, holes, proportions and lettering location. '
          'Geometric conventions: Z up, front is negative Y, physical right side is positive X; no mirror-derived back view. '
          'Design brief (facts and interpretation already separated by Codex):\n' + json.dumps(brief, ensure_ascii=False, indent=2))
        out = {}
        for name, cameras in CAMERAS.items():
            p = folder / ('prompt-' + name + '.txt')
            content = common + '\nViews: ' + cameras
            if name == 'volume':
                content += '\nAttach the accepted elevations board as identity reference. Show the same sculpture, not a redesign.'
            if p.exists() and p.read_text() != content + '\n': raise ValueError('Prompt changed; create a new revision.')
            if not p.exists(): p.write_text(content + '\n')
            out[name] = str(p)
        return {'prompts': out, 'required_views': ['front','right','back','top','bottom','three-quarter'],
          'execution': 'Codex uses built-in imagegen: elevations first; volume uses the first board as reference. Inspect consistency. Copy/register both originals; no local image synthesis.'}
