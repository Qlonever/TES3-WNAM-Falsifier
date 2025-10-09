import math
import struct
import os
import sys
import getopt

def sb(s):
    return s.encode('ascii')

def pack(*args):
    args = list(args)
    for i in range(len(args)):
        if type(args[i]) == str:
            args[i] = args[i].encode('ascii')
    return bytearray(struct.pack(*args))

def unpack(*args):
    ret = list(struct.unpack(*args))
    for i in range(len(ret)):
        if type(ret[i]) == bytes:
            ret[i] = ret[i].decode('ascii')
    return tuple(ret)

class ColorTable():

    def getSize(self):
        self.size = len(self.value) * 4

    def to_bytes(self):
        b = bytearray()
        for color in self.value:
            b += bytearray(color)
        return b

    def from_bytes(self, b):
        v = []
        for i in range(int(self.size/4)):
            i *= 4
            v.append(list(b[i:i+4]))
        return v

    def __init__(self, i):
        if type(i) == bytearray or type(i) == bytes:
            self.size = len(i)
            self.value = self.from_bytes(i)
        else:
            self.value = i
            if not hasattr(self, 'size'):
                self.getSize()

# Keep this as bytes so we don't use a lot of memory
class PixelArray():

    def getSize(self):
        self.size = self.height * self.padWidth

    def to_bytes(self, v):
        b = bytearray()
        for row in v:
            b += bytearray(row) + bytearray(self.padWidth - self.width)
        return b

    def from_bytes(self):
        v = []
        for i in range(self.height):
            i *= self.padWidth
            v.append(list(self.value[i:i + self.width]))
        return v

    def getRow(self, x, y, length):
        if not length:
            x = 0
            length = self.width
        baseRow = y * self.padWidth
        baseColumn = baseRow + x
        return self.value[baseColumn:baseColumn+length]

    def setRow(self, x, y, b):
        b = b[:self.width - x]
        baseRow = y * self.padWidth
        baseColumn = baseRow + x
        self.value[baseColumn:baseColumn+len(b)] = b

    def impose(self, pixelArray, x, y):
        for h in range(pixelArray.height):
            b = pixelArray.getRow(0, h, 0)
            self.setRow(x, y + h, b)

    def crop(self, x, y, width, height):
        cropped = []
        for h in range(height):
            cropped.append(self.getRow(x, y + h, width))
        return PixelArray(cropped, width, height, width)

    def __init__(self, i, width, height, padWidth):
        self.width = int(width)
        self.height = int(height)
        self.padWidth = int(padWidth)
        if not(type(i) == bytearray or type(i) == bytes):
            if not hasattr(self, 'size'):
                self.getSize()
            self.value = self.to_bytes(i)
        else:
            self.size = len(i)
            self.value = i

def padLength(length, pad):
    return int(pad * math.ceil(length/pad))

def createPalette(unsigned):
    palette = []
    for i in range(256):
        if unsigned:
            if i >= 128:
                i -= 128
            else:
                i += 128
        palette.append([i, i, i, 0])
    return palette

header = {
    'Signature':        {'format': '<2s', 'value': 'BM', 'error': 'Not a valid .BMP file.'},
    'FileSize':         {'format': '<I', 'value': 0x04A2},
    'Reserved':         {'format': '<I', 'value': 0x00},
    'DataOffset':       {'format': '<I', 'value': 0x0436},
    'InfoSize':         {'format': '<I', 'value': 0x28, 'error': 'Incompatible header.'},
    'Width':            {'format': '<I', 'value': 0x09},
    'Height':           {'format': '<I', 'value': 0x09},
    'Planes':           {'format': '<H', 'value': 0x01, 'error': 'Too many/no planes.'},
    'BitsPerPixel':     {'format': '<H', 'value': 0x08, 'error': 'Only 8bpp paletted images are supported.'},
    'Compression':      {'format': '<I', 'value': 0x00, 'error': 'Compressed images aren\'t supported.'},
    'ImageSize':        {'format': '<I', 'value': 0x6C},
    'XpixelsPerM':      {'format': '<I', 'value': 0x0EC4},
    'YpixelsPerM':      {'format': '<I', 'value': 0x0EC4},
    'ColorsUsed':       {'format': '<I', 'value': 0x0100},
    'ImportantColors':  {'format': '<I', 'value': 0x0100},
}

def parseHeader(b):
    offset = 0
    for item in header:
        itemFormat = header[item]['format']
        default = header[item]['value']
        size = struct.calcsize(itemFormat)
        itemBytes = b[offset:offset+size]
        data, = unpack(itemFormat, itemBytes)

        if data != default and 'error' in header[item]:
            print(header[item]['error'])
            return False
            
        header[item]['value'] = data
        offset += size

def WNAMsFromBMP(bmpPath, coords):
    pixelArray = None
    with open(bmpPath, mode='rb') as img:
        if parseHeader(img.read(0x36)) == False:
            return False
        palette = ColorTable(img.read(header['ColorsUsed']['value'] * 4))
        size = header['ImageSize']['value']
        width = header['Width']['value']
        height = header['Height']['value']
        if width % 9 > 0 or height % 9 > 0:
            print('Image dimensions must be divisible by 9.')
            return False
        padWidth = size / height
        if size == 0:
            # We'll assume that image editors pad rows to multiples of 4 bytes
            padWidth = padLength(width, 4)
            size = padWidth * height
        pixelList = list(img.read(size))
        b = bytearray()
        # I wish I could rely on image editors preserving color indices
        for pixel in pixelList:
            value = palette.value[pixel][0]
            if value >= 128:
                value -= 128
            else:
                value += 128
            b.append(value)
        pixelArray = PixelArray(b, width, height, padWidth)

    cellWidth = int(width / 9)
    cellHeight = int(height / 9)

    WNAMs = {}

    for x in range(cellWidth):
        for y in range(cellHeight):
            key = str(coords[0]+x) + ',' + str(coords[1]+y)
            data = pixelArray.crop(x*9,y*9,9,9).value
            subrecord = {'type':'WNAM', 'data':data}
            WNAMs[key] = subrecord

    return WNAMs

def BMPFromPixelArray(bmpPath, pixelArray, unsigned):
    b = bytearray()
    for item in header:
        itemFormat = header[item]['format']
        default = header[item]['value']
        value = default
        if item == 'FileSize':
            value = 0x436 + pixelArray.height * pixelArray.padWidth
        elif item == 'Width':
            value = pixelArray.width
        elif item == 'Height':
            value = pixelArray.height
        elif item == 'ImageSize':
            value = pixelArray.height * pixelArray.padWidth
        b += pack(itemFormat, value)
    palette = createPalette(unsigned)
    b += ColorTable(palette).to_bytes()
    b += pixelArray.value
    with open(bmpPath, mode='wb') as img:
        img.write(b)

defaultLAND = {
    'type':'LAND',
    'flags':pack('<I', 0),
    'subrecords':[
        {'type':'INTV', 'data':pack('<2i', 0, 0)},
        {'type':'DATA', 'data':pack('<I', 1)},
        {'type':'VNML', 'data':pack('>3b', 0, 0, 127) * 4225},
        {'type':'VHGT', 'data':pack('<f4225b3x', -256, *bytes(4225))},
        {'type':'WNAM', 'data':pack('<81b', *([-128] * 81))}
    ]
}

# Record structure:
#{
#    'type': 4 character string,
#    'flags': int containing bit flags,
#    'subrecords': [
#        subrecord,
#        ...
#    ]
#}
#
# Subrecord structure:
#
#{
#    'type': 4 character string,
#    'data': byte data of subrecord
#}

def packSubrecord(subrecord):
    data = subrecord['data']
    size = len(data)
    b = pack('<4sI', subrecord['type'], size)
    b += data
    return b

def packRecord(record):
    recordSize = 0
    recordInfo = pack('<4s8xI', record['type'], record['flags'])
    b = bytearray()
    for subrecord in record['subrecords']:
        b += packSubrecord(subrecord)
    recordInfo[4:8] = pack('<I', len(b))
    b = recordInfo + b
    return b

def subrecordsByType(record):
    subrecords = {}
    for subrecord in record['subrecords']:
        if not subrecord['type'] in subrecords:
            subrecords[subrecord['type']] = []
        subrecords[subrecord['type']].append(subrecord['data'])
    return subrecords

def replaceSubrecord(record, rep, n=1):
    num = 0
    for i in range(len(record['subrecords'])):
        subrecord = record['subrecords'][i]
        if subrecord['type'] == rep['type']:
            num += 1
            if num == n:
                record['subrecords'][i] = rep
                return record
    record['subrecords'].append(rep)
    return record

def parseRecord(b, recordType, flags):
    record = {'type':recordType, 'flags':flags, 'subrecords':[]}
    offset = 0
    while offset < len(b):
        subtype, size = unpack('<4sI', b[offset:offset+8])
        offset += 8
        subrecord = {'type':subtype, 'data':b[offset:offset+size]}
        offset += size
        record['subrecords'].append(subrecord)
    return record

def recordsFromPlugin(pluginPath, recordTypes):
    records = {}
    fileSize = os.path.getsize(pluginPath)
    with open(pluginPath, mode='rb') as f:
        offset = 0
        while offset < fileSize:
            recordType, recordSize, flags = unpack('<4sI4xI', f.read(0x10))
            if recordType in recordTypes:
                if not recordType in records:
                    records[recordType] = {}
                key = str(offset)
                b = f.read(recordSize)
                record = parseRecord(b, recordType, flags)
                if recordType == 'LAND':
                    x, y = unpack('<2i', b[8:16])
                    key = str(x) + ',' + str(y)

                records[recordType][key] = record
            else:
                f.seek(recordSize, 1)
            offset += 16 + recordSize
    return records

def sanitizeLand(records):
    for coords in records:
        record = records[coords]
        if record['type'] == 'LAND' and not ('WNAM' in subrecordsByType(record)):
            flag, = unpack('<I', subrecordsByType(record)['DATA'][0])
            flag = flag | 1
            record = replaceSubrecord(record, {'type':'DATA', 'data':pack('<I', flag)})
            record = replaceSubrecord(record, defaultLAND['subrecords'][2])
            record = replaceSubrecord(record, defaultLAND['subrecords'][3])
            record = replaceSubrecord(record, defaultLAND['subrecords'][4])
            records[coords] = record
    return records

def pluginToBMP(pluginPath, bmpDir, unsigned=True):
    records = recordsFromPlugin(pluginPath, ['LAND'])['LAND']
    records = sanitizeLand(records)
    if len(records) <= 0:
        print('Plugin does not contain any valid LAND records.')
        return
    # I hope nobody ever makes landmasses 100000 cells away from Vvardenfell
    left = 100000
    right = -100000
    bottom = 100000
    top = -100000
    for coords in records:
        coords = coords.split(',')
        x = int(coords[0])
        y = int(coords[1])
        left = min(x, left)
        right = max(x, right)
        bottom = min(y, bottom)
        top = max(y, top)
    cellWidth = right - left
    cellHeight = top - bottom
    width = cellWidth * 9
    height = cellHeight * 9
    padWidth = padLength(width, 4)
    image = PixelArray(bytearray(padWidth * height), width, height, padWidth)
    for x in range(cellWidth):
        worldX = x + left
        for y in range(cellHeight):
            worldY = y + bottom
            key = str(worldX) + ',' + str(worldY)
            b = None
            if key in records:
                b = subrecordsByType(records[key])['WNAM'][0]
            else:
                b = bytearray(81)
            cellArray = PixelArray(b, 9, 9, 9)
            image.impose(cellArray, x*9, y*9)
    bmpPath = bmpDir + '/' + str(left) + ',' + str(bottom) + '.bmp'
    BMPFromPixelArray(bmpPath, image, unsigned)
    print('Converted WNAMs to BMP at "' + bmpPath + '"')

def BMPToPlugin(masterPath, bmpPath, pluginPath):
    baseCoords = bmpPath.split('/')[-1].split('.')[0].split(',')
    if len(baseCoords) != 2:
        print('The image isn\'t named according to a cell coordinate.')
        return False
    x = int(baseCoords[0])
    y = int(baseCoords[1])
    imageWNAMs = WNAMsFromBMP(bmpPath, (x,y))
    oldRecords = recordsFromPlugin(masterPath, ['TES3', 'LAND', 'LTEX'])

    newRecords = {'TES3':{}}
    if 'LTEX' in oldRecords:
        newRecords['LTEX'] = oldRecords['LTEX']
    
    oldLandRecords = sanitizeLand(oldRecords['LAND'])
    newLandRecords = {}
    for coords in oldLandRecords:
        if coords in imageWNAMs:
            oldLandRecord = oldLandRecords[coords]
            oldWNAM = subrecordsByType(oldLandRecord)['WNAM'][0]
            imageWNAM = imageWNAMs[coords]
            if oldWNAM != imageWNAM['data']:
                newRecord = oldLandRecord
                newRecord = replaceSubrecord(newRecord, imageWNAM)
                newLandRecords[coords] = newRecord
    if len(newLandRecords) <= 0:
        print('The heightmap was not altered. No plugin will be generated.')
    else:
        newRecords['LAND'] = newLandRecords
        
        masters = {
            'Morrowind.esm':79837557
        }
        # Shan't compare Python's double-precision floats to plugins' single precision floats
        baseVersion, = unpack('<f', pack('<f', 1.2))
        version = baseVersion
        masterVersion, = unpack('<f', subrecordsByType(oldRecords['TES3']['0'])['HEDR'][0][0:4])
        version = max(version, masterVersion)
        if version > baseVersion:
            masters['Tribunal.esm'] = 4565686
            masters['Bloodmoon.esm'] = 9631798
        
        masterSize = os.path.getsize(masterPath)
        masterName = masterPath.split('/')[-1]

        isBase = False
        for master in masters:
            if masterName.lower() == master.lower():
                isBase = True
        
        if not isBase:
            masters[masterName] = masterSize

        recordCount = len(newRecords['LAND'])
        if 'LTEX' in newRecords:
            recordCount += len(newRecords['LTEX'])
        
        headerSubrecords = [
            {'type':'HEDR', 'data':pack('<fI32s256sI', version, 0, '', '', recordCount)}
        ]

        for master in masters:
            size = masters[master]
            headerSubrecords.append({'type':'MAST', 'data':pack('<' + str(len(master) + 1) + 's', master)})
            headerSubrecords.append({'type':'DATA', 'data':pack('<Q', size)})

        newRecords['TES3']['0'] = {
            'type':'TES3',
            'flags':0,
            'subrecords':headerSubrecords
        }

        with open(pluginPath, mode='wb') as f:
            for recordType in newRecords:
                for recordName in newRecords[recordType]:
                    record = newRecords[recordType][recordName]
                    f.write(packRecord(record))

        print('Created new plugin at "' + pluginPath + '"')
            
def verifyPath(path):
    if not path:
        return False
    filename = False
    extension = False
    path = path.replace('\\', '/')
    split = path.split('/')
    if '.' in split[-1]:
        filename = split[-1]
        extension = filename.split('.')[-1].lower()
        del split[-1]
    directory = '/'.join(split)
    if os.path.exists(directory):
        return [path, directory, filename, extension]
    else:
        print('Invalid path: "' + path + '"')
        return False

def main(argv):
    usage = 'Usage: WNAMtool.py --extract -i [input plugin path] -b [bmp output dir] \n                   --repack  -i [input plugin path] -b [bmp image path] -o [output plugin path]'

    opts, args = getopt.getopt(argv, 'i:b:o:', longopts=['extract', 'repack'])
    d = {
        'mode':False,
        '-i':False,
        '-b':False,
        '-o':False
    }
    for opt, arg in opts:
        if opt in ['--extract', '--repack']:
            d['mode'] = opt
        else:
            d[opt] = arg

    i = verifyPath(d['-i'])
    b = verifyPath(d['-b'])
    o = verifyPath(d['-o'])
        
    if d['mode'] == '--extract':
        if b and i and i[2] and i[3] in ['esp', 'esm']:
            pluginToBMP(i[0], b[1])
            return
    elif d['mode'] == '--repack':
        if i and i[2] and i[3] in ['esp', 'esm'] and b and b[2] and b[3] == 'bmp' and o and o[2] and o[3] in ['esp', 'esm']:
            BMPToPlugin(i[0], b[0], o[0])
            return
    print(usage)

main(sys.argv[1:])
