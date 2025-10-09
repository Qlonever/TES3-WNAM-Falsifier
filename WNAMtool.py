import math
import os
import sys
import getopt

class Data:
    signed = False
    
    def getSize(self):
        self.size = len(self.value)
    
    def to_bytes(self):
        return self.value.to_bytes(self.size, byteorder='little', signed=self.signed)
    
    def from_bytes(self, b):
        return int.from_bytes(b, byteorder='little', signed=self.signed)
        
    def __init__(self, i):
        if type(i) == bytearray or type(i) == bytes:
            self.size = len(i)
            self.value = self.from_bytes(i)
        else:
            self.value = i
            if not hasattr(self, 'size'):
                self.getSize()

class String(Data):
    def to_bytes(self):
        return bytes(self.value, 'ascii') + bytes([0] * (self.size - len(self.value)))
    
    def from_bytes(self, b):
        return b.decode('ascii')

class Int8(Data):
    size = 1
    signed = True

class Int32(Data):
    size = 4
    signed = True
    
class Uint8(Data):
    size = 1
    signed = False
    
class Uint16(Data):
    size = 2
    signed = False
    
class Uint32(Data):
    size = 4
    signed = False

class Uint64(Data):
    size = 8
    signed = False
    
class ColorTable(Data):

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

# Keep this as bytes so we don't use gigabytes of memory 
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
    'Signature':        {'class': String, 'value': 'BM', 'error': 'Not a valid .BMP file.'},
    'FileSize':         {'class': Uint32, 'value': 0x04A2},
    'Reserved':         {'class': Uint32, 'value': 0x00},
    'DataOffset':       {'class': Uint32, 'value': 0x0436},
    'InfoSize':         {'class': Uint32, 'value': 0x28, 'error': 'Incompatible header.'},
    'Width':            {'class': Uint32, 'value': 0x09},
    'Height':           {'class': Uint32, 'value': 0x09},
    'Planes':           {'class': Uint16, 'value': 0x01, 'error': 'Too many/no planes.'},
    'BitsPerPixel':     {'class': Uint16, 'value': 0x08, 'error': 'Only 8bpp paletted images are supported.'},
    'Compression':      {'class': Uint32, 'value': 0x00, 'error': 'Compressed images aren\'t supported.'},
    'ImageSize':        {'class': Uint32, 'value': 0x6C},
    'XpixelsPerM':      {'class': Uint32, 'value': 0x0EC4},
    'YpixelsPerM':      {'class': Uint32, 'value': 0x0EC4},
    'ColorsUsed':       {'class': Uint32, 'value': 0x0100},
    'ImportantColors':  {'class': Uint32, 'value': 0x0100},
}

def parseHeader(b):
    read = 0
    for item in header:
        itemClass = header[item]['class']
        default = header[item]['value']
        size = 0
        if itemClass == String:
            size = 2
        else:
            size = itemClass.size
        itemBytes = b[read:read+size]
        data = itemClass(itemBytes)

        if data.value != default and 'error' in header[item]:
            print(header[item]['error'])
            return False
            
        header[item]['value'] = data.value
        read += size

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
        b = []
        # I wish I could rely on image editors preserving color indices
        for pixel in pixelList:
            value = palette.value[pixel][0]
            if value >= 128:
                value -= 128
            else:
                value += 128
            b.append(value)
        b = bytes(b)
        pixelArray = PixelArray(b, width, height, padWidth)

    cellWidth = int(width / 9)
    cellHeight = int(height / 9)

    WNAMs = {}
    
    for x in range(cellWidth):
        for y in range(cellHeight):
            key = str(coords[0]+x) + ',' + str(coords[1]+y)
            WNAMs[key] = pixelArray.crop(x*9,y*9,9,9).value

    return WNAMs

def BMPFromPixelArray(bmpPath, pixelArray, unsigned):
    b = bytearray()
    for item in header:
        itemClass = header[item]['class']
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
        b += itemClass(value).to_bytes()
    palette = createPalette(unsigned)
    b += ColorTable(palette).to_bytes()
    b += pixelArray.value
    with open(bmpPath, mode='wb') as img:
        img.write(b)

defaultLAND = {
    'type':'LAND',
    'subrecords':{
        'INTV':Int32(0).to_bytes() * 2,
        'DATA':Uint32(1).to_bytes(),
        'VNML':bytearray([0, 0, 127] * 4225),
        'VHGT':bytearray(b'\x00\x00\x80\xC3') + bytes(4228),
        'WNAM':bytearray([128]*81)
    }
}

def parseRecord(b, recordType):
    record = {'type':recordType, 'subrecords':{}}
    offset = 0
    while offset < len(b):
        subtype = String(b[offset:offset+4]).value
        offset += 4
        size = Uint32(b[offset:offset+4]).value
        offset += 4
        data = b[offset:offset+size]
        offset += size
        record['subrecords'][subtype] = data
    return record

def landRecordsFromPlugin(pluginPath):
    records = {'LAND':{}, 'LTEX':[]}
    fileSize = os.path.getsize(pluginPath)
    with open(pluginPath, mode='rb') as f:
        offset = 0
        while offset < fileSize:
            recordType = String(f.read(4)).value
            recordSize = Uint32(f.read(4)).value
            f.seek(4, 1)
            flags = f.read(4)
            if recordType == 'LAND':
                b = f.read(recordSize)
                x = Int32(b[8:12]).value
                y = Int32(b[12:16]).value
                key = str(x) + ',' + str(y)
                record = parseRecord(b, 'LAND')
                if not ('WNAM' in record['subrecords']):
                    flag = Uint32(record['subrecords']['DATA'])
                    flag.value = flag.value | 1
                    record['subrecords']['DATA'] = flag.to_bytes()
                    record['subrecords']['VNML'] = defaultLAND['subrecords']['VNML']
                    record['subrecords']['VHGT'] = defaultLAND['subrecords']['VHGT']
                    record['subrecords']['WNAM'] = defaultLAND['subrecords']['WNAM']
                    
                records['LAND'][key] = record
            elif recordType == 'LTEX':
                b = f.read(recordSize)
                records['LTEX'].append(parseRecord(b, 'LTEX'))
            else:
                f.seek(recordSize, 1)
            offset += 16 + recordSize
    return records

def pluginToBMP(pluginPath, bmpDir, unsigned=True):
    records = landRecordsFromPlugin(pluginPath)['LAND']
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
                b = records[key]['subrecords']['WNAM']
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
    oldRecords = landRecordsFromPlugin(masterPath)
    oldLandRecords = oldRecords['LAND']
    textureRecords = oldRecords['LTEX']
    newLandRecords = {}
    for coords in oldLandRecords:
        if coords in imageWNAMs:
            oldLandRecord = oldLandRecords[coords]
            oldWNAM = oldLandRecord['subrecords']['WNAM']
            imageWNAM = imageWNAMs[coords]
            if oldWNAM != imageWNAM:
                newRecord = oldLandRecord
                newRecord['subrecords']['WNAM'] = imageWNAM
                newLandRecords[coords] = newRecord
    if len(newLandRecords) <= 0:
        print('The heightmap was not altered. No plugin will be generated.')
    else:    
        masterSize = os.path.getsize(masterPath)
        masterName = masterPath.split('/')[-1]
        masterRecordSize = 0
        if masterName.lower() in ['morrowind.esm', 'tribunal.esm', 'bloodmoon.esm']:
            masterName = ''
        else:
            masterRecordSize = 0x19 + len(masterName)

        def writeMaster(name, size):
            master = bytearray()
            master += String('MAST').to_bytes()
            master += Uint32(len(name)+1).to_bytes()
            master += String(name).to_bytes()
            master += bytes(1)
            master += String('DATA').to_bytes()
            master += Uint32(0x8).to_bytes()
            master += Uint64(size).to_bytes()
            return master

        def writeRecord(record):
            recordSize = 0
            recordBytes = bytearray()
            recordBytes += String(record['type']).to_bytes()
            recordBytes += bytes(0xC)
            for subtype in record['subrecords']:
                subrecord = record['subrecords'][subtype]
                recordSize += 0x8 + len(subrecord)
                recordBytes += String(subtype).to_bytes()
                recordBytes += Uint32(len(subrecord)).to_bytes()
                recordBytes += subrecord
            recordBytes[4:8] = Uint32(recordSize).to_bytes()
            return recordBytes

        with open(pluginPath, mode='wb') as f:
            f.write(String('TES3').to_bytes())
            f.write(Uint32(0x1A5 + masterRecordSize).to_bytes())
            f.write(bytes(8))
            f.write(String('HEDR').to_bytes())
            f.write(Uint32(0x12C).to_bytes())
            f.write(bytes([0x66, 0x66, 0xA6, 0x3F]))
            f.write(bytes(0x124))
            f.write(Uint32(len(newLandRecords) + len(textureRecords)).to_bytes())

            f.write(writeMaster('Morrowind.esm', 79837557))
            f.write(writeMaster('Tribunal.esm', 4565686))
            f.write(writeMaster('Bloodmoon.esm', 9631798))

            if len(masterName) > 0:
                f.write(writeMaster(masterName, masterSize))
            
            for coords in newLandRecords:
                f.write(writeRecord(newLandRecords[coords]))
            for record in textureRecords:
                f.write(writeRecord(record))

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

    try:
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
    except:
        print(usage)

main(sys.argv[1:])
