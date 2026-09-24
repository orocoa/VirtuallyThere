# A technical example, never a default template for every user's story.
from vt.blender_geometry import loft,ellipsoid,fuse,flat_bottom
left=loft('low',[(0,-16,0,20,20),(12,-18,0,22,21),(35,-22,0,22,20),(54,-19,0,20,18),(61,-16,0,13,13),(63,-16,0,2,2)])
right=loft('high',[(0,23,4,12,17),(20,27,5,13,18),(45,24,6,12,17),(66,17,8,11,15),(80,13,8,9,12),(83,13,8,2,2)])
join=ellipsoid('junction',(2,1,-5),(35,19,20))
obj=flat_bottom(fuse([left,right,join],voxel=.55,smooth=8))
obj.name='VT_MODEL'
