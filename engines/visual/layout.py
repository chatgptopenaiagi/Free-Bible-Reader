"""Bounded SVG projection of upstream arc-layout/arc-shaders/vote-weight math.

Original: trekhleb/bible-cross-references, MIT, commit 23bf0908858c949e519abe7a4ce7f4492f5fb3ba.
This local adapter samples the same half-ellipse formula instead of using WebGL.
"""
import math

def vote_weight(votes):
    return min(1.0,0.2+0.8*math.log10(1+max(votes,0))/2)

def compute_layout(width=1000,height=420,verse_count=31102):
    width=float(width);height=float(height)
    if not math.isfinite(width)or not math.isfinite(height):raise ValueError('Finite dimensions required')
    width=max(240,min(width,2400));height=max(180,min(height,1200))
    vertical=height>width*1.15
    baseline=64.0 if vertical else height-58.0
    return {'layout_id':'upstream-half-ellipse-v1','orientation':'vertical'if vertical else'horizontal','width':width,'height':height,
      'axis_start':48.0 if vertical else 32.0,'axis_end':height-16.0 if vertical else width-32.0,
      'baseline':baseline,'max_arc_height':max(width-baseline-16.0,0)if vertical else max(baseline-16.0,0),
      'view_start':0.0,'view_end':float(verse_count),'verse_count':verse_count,
      'algorithm_source':'src/visualizations/arcs/arc-layout.ts;src/visualizations/arcs/arc-shaders.ts',
      'adaptation':'Bounded SVG polyline sampling of upstream half-ellipse; not the original all-link GPU renderer.'}

def along(layout,index):
    return layout['axis_start']+(index-layout['view_start'])/(layout['view_end']-layout['view_start'])*(layout['axis_end']-layout['axis_start'])

def point(layout,index):
    a=along(layout,index)
    return (layout['baseline'],a)if layout['orientation']=='vertical'else(a,layout['baseline'])

def arc_geometry(layout,source_index,target_start,target_end,segments=32):
    a=along(layout,source_index+0.5);b=along(layout,(target_start+target_end+1)/2)
    radius=(b-a)/2;height=min(abs(radius),layout['max_arc_height']);points=[]
    for i in range(segments+1):
        theta=math.pi*i/segments
        ax=(a+b)/2-radius*math.cos(theta);rise=height*math.sin(theta)
        xy=(layout['baseline']+rise,ax)if layout['orientation']=='vertical'else(ax,layout['baseline']-rise)
        points.append([round(xy[0],6),round(xy[1],6)])
    return {'source_index':source_index,'target_start_index':target_start,'target_end_index':target_end,
      'source_center':source_index+0.5,'target_center':(target_start+target_end+1)/2,
      'arc_height':height,'points':points,'path':' '.join(('M'if i==0 else'L')+f'{xy[0]},{xy[1]}'for i,xy in enumerate(points))}
