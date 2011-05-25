#!/usr/bin/python

__author__ = 'Martin Samsula'
__email__ = '<martin@falanxia.com>'

import sys
import glob
import math
import xml.etree.ElementTree
import os
import os.path

try:
    import simplejson
except:
    import json
    simplejson = json
def ds(data): return simplejson.dumps(data, indent=4, default=str)

from PIL import Image


print 'usage: python merge.py collision_tile [source_dir(default:src)]'

collision_tile = sys.argv[1]
src_dir = sys.argv[2] if len(sys.argv) > 2 else 'src'
output_dir = 'output'

try:
    os.makedirs(output_dir)
except os.error:
    pass

src_files = os.path.join(src_dir, '*.tmx')



class TileSet():
    """obrazek mapa tilu"""
    def __init__(self):
        self.name = ''
        self.tile_width = 0
        self.tile_height = 0
        self.source = ''
        self.width = 0
        self.height = 0
        self.first_gid = 0
        self.collision_tile = 0
        self._image = None
        self._cut_tiles = {}

    def out(self):
        return {'name': self.name,
                'tile_width': self.tile_width,
                'tile_height': self.tile_height,
                'source': self.source,
                'width': self.width,
                'height': self.height,
                'first_gid': self.first_gid,
                'collision_tile': self.collision_tile}

    @property
    def tiles_count(self):
        return (self.width / self.tile_width) * (self.height / self.tile_height)

    def get_new_tile_image(self):
        return Image.new('RGBA', (self.tile_width, self.tile_height), (0, 0, 0, 0))

    def get_tile_set_image(self):
        if not self._image:
            self._image = Image.open(os.path.join(src_dir, self.source))
        return self._image

    def get_tile_image(self, index):
        index -= self.first_gid
        left = (self.tile_width * index) % self.width
        top = (self.tile_width * index) / self.width * self.tile_height
        if index not in self._cut_tiles:
            self._cut_tiles[index] = self.get_tile_set_image().crop((left, top, left+32, top+32))
        return self._cut_tiles[index]


class Tile():
    def __init__(self):
        self.id = 0


class MergeSet(list):
    """list id tilu ktere se slepuji dohromady"""
    def __init__(self, l):
        list.__init__(self, l)
        self.image = None
        self.original_positions = {}
        self.collision = 0

    def set_position(self, file, pos):
        if file not in self.original_positions:
            self.original_positions[file] = []
        self.original_positions[file].append(pos)


class Layer():
    def __init__(self):
        self.tiles = [Tile()]
        self.name = ''

    def out(self):
        return {'name': self.name, 'first_100_tiles': ','.join(list(str(item.id) for item in self.tiles[0:100]))}


class LevelMap():
    def __init__(self):
        self.tile_set = TileSet()
        self.layers = [Layer()]
        self.file = ''

    def out(self):
        return {'tile_set': self.tile_set.out(), 'layers': list(item.out() for item in self.layers)}

    @property
    def tiles_count(self):
        return len(self.layers[0].tiles)

    def get_merge_sets(self):
        merge_sets = []
        for i in range(0, self.tiles_count):
            merge_set = []
            for layer in self.layers:
                merge_set.append(layer.tiles[i].id)
            merge_set = filter(None, merge_set)
            merge_sets.append(merge_set)
        return merge_sets



class Composer():

    TITLESET_MAX_WIDTH = 1024

    def __init__(self):
        self.lmap = LevelMap()
        self.merge_sets = []
        self.final = TileSet()


    def _is_included(self, merge_set):
        for check in self.merge_sets:
            if check[:] == merge_set[:]:
                return check
        merge_set = MergeSet(merge_set)
        self.merge_sets.append(merge_set)
        return merge_set


    def merge_tiles(self, lmap):
        assert isinstance(lmap, LevelMap)
        self.lmap = lmap
        i = -1
        for merge_set in self.lmap.get_merge_sets():
            i += 1

            # get_merge_sets() nam vraci i prazdne sety, potrebuje si ale drzet index i (pozici v mape levelu)
            if not merge_set:
                continue

            merge_set = self._is_included(merge_set)
            merge_set.set_position(self.lmap.file, i)

            for tile_id in merge_set:
                if tile_id >= self.lmap.tile_set.collision_tile:
                    merge_set.collision = 1

            merge_set.image = self.lmap.tile_set.get_new_tile_image()
            for tile_id in merge_set:
                if tile_id:
                    part_image = self.lmap.tile_set.get_tile_image(tile_id)
                    merge_set.image.paste(part_image, None, part_image)
            merge_set.image = merge_set.image.convert('RGB')


    def sort_by_collision(self):
        self.merge_sets = sorted(self.merge_sets, key=lambda x: x.collision)
        i = 0
        for merge_set in self.merge_sets:
            if merge_set.collision:
                break
            i += 1
        return i


    def make_new_tile_set(self):
        tiles_count = len(self.merge_sets)
        tiles_in_width = int(math.sqrt(tiles_count)) + 1
        self.final.width = tiles_in_width * self.lmap.tile_set.tile_width

        if self.final.width > self.TITLESET_MAX_WIDTH:
            # deleni na cela cisla
            tiles_in_width = self.TITLESET_MAX_WIDTH / self.lmap.tile_set.tile_width
            self.final.width = tiles_in_width * self.lmap.tile_set.tile_width

        tiles_in_height = (tiles_count / tiles_in_width) + 1
        self.final.height = tiles_in_height * self.lmap.tile_set.tile_height

        new_tile_set = Image.new('RGBA', (self.final.width, self.final.height), (0, 0, 0, 0))

        # zaciname na druhem tilu, prvni zustava transparentni
        left = self.lmap.tile_set.tile_width
        top = 0

        for merge_set in self.merge_sets:
            new_tile_set.paste(merge_set.image, (left, top))
            left += self.lmap.tile_set.tile_width
            if left >= self.final.width:
                left = 0
                top += self.lmap.tile_set.tile_height

        new_tile_set.save(os.path.join(output_dir, os.path.basename(self.lmap.tile_set.source)))



composer = Composer()


print 'parsing tmx files'
for file in glob.glob(src_files):
    print file
    lmap_xml = xml.etree.ElementTree.fromstring(open(file).read())
    lmap = LevelMap()
    lmap.layers = []
    lmap.file = file

    title_set = lmap_xml.find('tileset')
    image = title_set.find('image')
    lmap.tile_set = TileSet()
    lmap.tile_set.name = title_set.get('name')
    lmap.tile_set.collision_tile = int(collision_tile)
    lmap.tile_set.tile_height = int(title_set.get('tileheight'))
    lmap.tile_set.tile_width = int(title_set.get('tilewidth'))
    lmap.tile_set.first_gid = int(title_set.get('firstgid'))
    lmap.tile_set.source = image.get('source')
    lmap.tile_set.height = int(image.get('height'))
    lmap.tile_set.width = int(image.get('width'))

    for item in lmap_xml.getiterator('layer'):
        layer = Layer()
        layer.tiles = []
        layer.name = item.get('name')
        lmap.layers.append(layer)

        data = item.find('data')

        if data.get('compression'):
            print 'this script does not support tile data compression, pls use XML format'
            sys.exit()

        if data.get('compression') or data.get('encoding'):
            print 'this script does not support tile data encoding, pls use XML format'
            sys.exit()

        for dtile in data:
            tile = Tile()
            tile.id = int(dtile.get('gid'))
            layer.tiles.append(tile)

#    print ds(lmap.out())

    if not lmap.layers:
        continue

    print 'working on level part', lmap.file
    print 'tiles in level map:', lmap.tiles_count
    print 'tiles in original tile set:', lmap.tile_set.tiles_count

    print 'merging layers...',
    composer.merge_tiles(lmap)
    print 'done'



if not composer.merge_sets:
    print 'nothing to merge'
    sys.exit()

print 'new merged unique tiles:', len(composer.merge_sets)

print 'composing final tileset image...'
collision_tile = composer.sort_by_collision()
print 'first collision tile:', collision_tile
composer.make_new_tile_set()
print 'final tile set width:', composer.final.width, ', height:', composer.final.height
print 'done'



#for merge_set in composer.merge_sets:
#    print merge_set.collision



print 'composing changed tmx templates...',

for file in glob.glob(src_files):
    lmap_xml = xml.etree.ElementTree.fromstring(open(file).read())
    tile_set = lmap_xml.find('tileset')
    tile_set.set('collision_tile', str(collision_tile + 1 + lmap.tile_set.first_gid))

    image = tile_set.find('image')
    image.set('width', str(composer.final.width))
    image.set('height', str(composer.final.height))

    first_layer = lmap_xml.find('layer')
    first_layer.set('name', 'walls')

    i = 0
    for tile in list(first_layer.find('data')):
        tile.set('gid', str(0))
        for merge_set in composer.merge_sets:
            if file in merge_set.original_positions and i in merge_set.original_positions[file]:
                tile.set('gid', str(composer.merge_sets.index(merge_set) + 1 + lmap.tile_set.first_gid))
                break
        i += 1

    # smazani ostatnich layeru
    i = 0
    for layer in lmap_xml.getiterator('layer'):
        if i >= 1:
            lmap_xml.remove(layer)
        i += 1

    open(os.path.join(output_dir, os.path.basename(file)), 'w').write(xml.etree.ElementTree.tostring(lmap_xml))

print 'done'


