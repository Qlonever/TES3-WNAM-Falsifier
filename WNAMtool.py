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
        if isinstance(args[i], str):
            args[i] = args[i].encode('ascii')
    return bytearray(struct.pack(*args))

def unpack(*args):
    ret = list(struct.unpack(*args))
    for i in range(len(ret)):
        if isinstance(ret[i], bytes):
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
        if isinstance(i, (bytes, bytearray)):
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
        if not isinstance(i, (bytes, bytearray)):
            if not hasattr(self, 'size'):
                self.getSize()
            self.value = self.to_bytes(i)
        else:
            self.size = len(i)
            self.value = i

class Subrecord():
    
    def pack(self):
        info = pack('<4sI', self.tag, len(self.data))
        return info + self.data

    def __repr__(self):
        return self.tag + ': ' + str(self.data)

    def __init__(self, i):
        if not i:
            return
        if isinstance(i, dict):
            self.tag = i['tag']
            self.data = i['data']
        else:
            self.tag, size = unpack('<4sI', i.read(8))
            self.data = bytearray(i.read(size))

# Record dict structure:
#{
#    'tag': 4 character string,
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
#    'tag': 4 character string,
#    'data': byte data of subrecord
#}

class Record():

    def pack(self):
        data = bytearray()
        for subrecord in self.subrecords:
            data += subrecord.pack()
        info = pack('<4sI4xI', self.tag, len(data), self.flags)
        return info + data

    def sortSubrecords(self):
        for subrecord in self.subrecords:
            if not subrecord.tag in self.subrecordsSorted:
                self.subrecordsSorted[subrecord.tag] = []
            self.subrecordsSorted[subrecord.tag].append(subrecord)

    def getSubrecord(self, tag, index=0):
        try:
            return self.subrecordsSorted[tag][index]
        except:
            return False

    def addSubrecord(self, subrecord):
        if not subrecord:
            return
        
        if isinstance(subrecord, dict):
            subrecord = Subrecord(subrecord)
        
        self.subrecords.append(subrecord)
        if not subrecord.tag in self.subrecordsSorted:
            self.subrecordsSorted[subrecord.tag] = []
        self.subrecordsSorted[subrecord.tag].append(subrecord)
        

    def setSubrecord(self, rep, index=0):
        if not rep:
            return
        
        if isinstance(rep, dict):
            rep = Subrecord(rep)
            
        if not rep.tag in self.subrecordsSorted or index >= len(self.subrecordsSorted[rep.tag]):
            self.addSubrecord(rep)
            return
        
        count = 0
        for i in range(len(self.subrecords)):
            subrecord = self.subrecords[i]
            if subrecord.tag == rep.tag:
                if count == index:
                    self.subrecords[i] = rep
                    self.subrecordsSorted[rep.tag][count] = rep
                    return
                count += 1
        return

    # Used to replace records, or identify them easily
    def setId(self):
        if self.tag == 'TES3':
            if hasattr(self, 'plugin'):
                self.id = self.plugin['name'].lower()
        elif self.tag == 'LAND':
            x, y = unpack('<2i', (self.getSubrecord('INTV').data))
            self.id = str(x) + ',' + str(y)
        elif self.tag == 'LTEX':
            index, = unpack('<I', self.getSubrecord('INTV').data)
            if hasattr(self, 'plugin'):
                self.id = self.plugin['name'] + ' '
            else:
                self.id = ''
            self.id += str(index)

    def getName(self):
        if hasattr(self, 'id'):
            return self.id
        return self.plugin['name'] + ' ' + str(self.plugin['offset'])

    def __repr__(self):
        text = self.tag + ': \n'
        text += 'flags: ' + str(self.flags) + '\n'
        text += 'subrecords: \n'
        for subrecord in self.subrecords:
            text += repr(subrecord) +'\n'

        return text

    def __init__(self, i, tags=False):
        if not i:
            return

        self.passed = False
        self.subrecords = []
        self.subrecordsSorted = {}
        
        if isinstance(i, dict):
            self.tag = i['tag']
            self.flags = i['flags']
            for subrecord in i['subrecords']:
                self.addSubrecord(subrecord)
        else:
            start = i.tell()
            info = i.read(0x10)
            if not info:
                self.passed = True
                return
            self.tag, size, self.flags = unpack('<4sI4xI', info)
            if tags and not self.tag in tags:
                i.seek(size, 1)
                self.passed = True
                return
            
            offset = i.tell()
            while offset < start + size + 0x10:
                subrecord = Subrecord(i)
                self.addSubrecord(subrecord)
                offset = i.tell()
            
            self.plugin = {'name':os.path.basename(i.name), 'offset':start}
        self.setId()

def padLength(length, pad):
    return int(pad * math.ceil(length/pad))

def createPalette(unsigned=True):
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

        pixelData = img.read(size)
        b = bytearray()
        # I wish I could rely on image editors preserving color indices
        for pixel in pixelData:
            value = palette.value[pixel][0]
            if value >= 128:
                value -= 128
            else:
                value += 128
            b.append(value)
        pixelArray = PixelArray(b, width, height, padWidth)
    
    WNAMs = {}

    cellWidth = int(width / 9)
    cellHeight = int(height / 9)

    for x in range(cellWidth):
        for y in range(cellHeight):
            key = str(coords[0]+x) + ',' + str(coords[1]+y)
            data = pixelArray.crop(x*9,y*9,9,9).value
            subrecord = Subrecord({'tag':'WNAM', 'data':data})
            WNAMs[key] = subrecord

    return WNAMs

def BMPFromPixelArray(bmpPath, pixelArray):
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
    palette = createPalette()
    b += ColorTable(palette).to_bytes()
    b += pixelArray.value
    with open(bmpPath, mode='wb') as img:
        img.write(b)

def recordsFromPlugins(pluginDict, recordTags=False):
    records = {'TES3':{}}
    for pluginName, pluginPath in pluginDict.items():
        with open(pluginPath, mode='rb') as f:
            header = Record(f)
            recordCount, = unpack('<296xI', header.getSubrecord('HEDR').data)
            records['TES3'][header.getName()] = header

            print('Reading ' + str(recordCount) + ' records from ' + pluginName + '... ', end='')
            
            for num in range(recordCount):
                record = Record(f, recordTags)
                if not record.passed:
                    if not record.tag in records:
                        records[record.tag] = {}
                            
                    key = record.getName()
                    records[record.tag][key] = record

            print('Done.')

    print('')
    return records

defaultLAND = Record({
    'tag':'LAND',
    'flags':0,
    'subrecords':[
        {'tag':'INTV', 'data':pack('<2i', 0, 0)},
        {'tag':'DATA', 'data':pack('<I', 1)},
        {'tag':'VNML', 'data':pack('>3b', 0, 0, 127) * 4225},
        {'tag':'VHGT', 'data':pack('<f4225b3x', -256, *bytes(4225))},
        {'tag':'WNAM', 'data':pack('<81b', *([-128] * 81))}
    ]
})

def sanitizeLand(records):
    for coords in records:
        record = records[coords]
        if record.tag == 'LAND' and not record.getSubrecord('WNAM'):
            flags, = unpack('<I', record.getSubrecord('DATA').data)
            flags = flags | 1
            record.setSubrecord(Subrecord({'tag':'DATA', 'data':pack('<I', flags)}))
            # Leaving these out doesn't cause any crashes
            #record.setSubrecord(defaultLAND.getSubrecord('VNML'))
            #record.setSubrecord(defaultLAND.getSubrecord('VHGT'))
            record.setSubrecord(defaultLAND.getSubrecord('WNAM'))
            records[coords] = record
    return records

def pluginsToBMP(pluginList, bmpDir):
    landRecords = recordsFromPlugins(pluginList, ['LAND'])['LAND']
    landRecords = sanitizeLand(landRecords)
    if len(landRecords) <= 0:
        return 'Couldn\'t find any LAND records in the provided plugin(s).'
    # I hope nobody ever makes landmasses 100000 cells away from Vvardenfell
    left = 100000
    right = -100000
    bottom = 100000
    top = -100000
    for coords in landRecords:
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
    mapArray = PixelArray(bytearray(padWidth * height), width, height, padWidth)
    for x in range(cellWidth):
        worldX = x + left
        for y in range(cellHeight):
            worldY = y + bottom
            key = str(worldX) + ',' + str(worldY)
            b = None
            if key in landRecords:
                b = landRecords[key].getSubrecord('WNAM').data
            else:
                b = bytearray(81)
            cellArray = PixelArray(b, 9, 9, 9)
            mapArray.impose(cellArray, x*9, y*9)
    bmpPath = '/'.join(filter(None, [bmpDir, str(left) + ',' + str(bottom) + '.bmp']))
    BMPFromPixelArray(bmpPath, mapArray)
    return 'Converted WNAMs to BMP at "' + bmpPath + '"'

def BMPToPlugin(mastersDict, bmpPath, pluginPath):
    baseCoords = bmpPath.split('/')[-1].split('.')[0].split(',')
    if len(baseCoords) != 2:
        return 'The image isn\'t named according to a cell coordinate.'
    x = int(baseCoords[0])
    y = int(baseCoords[1])
    imageWNAMs = WNAMsFromBMP(bmpPath, (x,y))
    oldRecords = recordsFromPlugins(mastersDict, ['TES3', 'LAND', 'LTEX'])

    newRecords = {'TES3':{}}
    
    oldLandRecords = sanitizeLand(oldRecords['LAND'])
    newLandRecords = {}

    oldTexRecords = oldRecords['LTEX']
    newTexRecords = {}

    texPaths = []

    version, = unpack('<f', pack('<f', 1.2))
    masters = {
        'Morrowind.esm':79837557
    }
    newMasters = {}

    for coords, imageWNAM in imageWNAMs.items():
        landRecord = None
        if not coords in oldLandRecords:
            if imageWNAM.data != bytearray(81):
                x, y = coords.split(',')
                coordSubrecord = Subrecord({'tag':'INTV', 'data':pack('<2i', int(x), int(y))})
                landRecord = Record({
                    'tag':'LAND',
                    'flags':0,
                    'subrecords':[
                        coordSubrecord,
                        defaultLAND.getSubrecord('DATA'),
                        #defaultLAND.getSubrecord('VNML'),
                        #defaultLAND.getSubrecord('VHGT'),
                        imageWNAM
                    ]
                })
        else:
            oldLandRecord = oldLandRecords[coords]
            oldWNAM = oldLandRecord.getSubrecord('WNAM')
            if oldWNAM.data != imageWNAM.data:
                landRecord = oldLandRecord
                landRecord.setSubrecord(imageWNAM)
                masterName = landRecord.plugin['name']
                masterPath = mastersDict[masterName.lower()]
                masterHeader = oldRecords['TES3'][masterName.lower()]
                masterVersion, = unpack('<f', masterHeader.getSubrecord('HEDR').data[0:4])
                if masterVersion > version:
                    version = masterVersion
                    masters['Tribunal.esm'] = 4565686
                    masters['Bloodmoon.esm'] = 9631798
                if not masterName.lower() in [n.lower() for n in masters]:
                    newMasters[masterName] = os.path.getsize(masterPath)

                oldVTEX = landRecord.getSubrecord('VTEX')
                if oldVTEX:
                    newTexNums = []
                    oldTexNums = list(unpack('<256H', oldVTEX.data))
                    for index in oldTexNums:
                        # Beware, VTEX indices are +1 from LTEX indices
                        if index == 0:
                            newTexNums.append(0)
                        else:
                            oldTexRecord = oldTexRecords[masterName + ' ' + str(index - 1)]
                            path = oldTexRecord.getSubrecord('DATA').data
                            path, = unpack('<' + str(len(path) - 1) + 'sx', path)
                            if not path in texPaths:
                                newTexRecord = Record({
                                    'tag':'LTEX',
                                    'flags':0,
                                    'subrecords':[
                                        {'tag':'NAME', 'data':pack('<4sx', str(len(texPaths)).zfill(4))},
                                        {'tag':'INTV', 'data':pack('<I', len(texPaths))},
                                        {'tag':'DATA', 'data':pack('<' + str(len(path)) + 'sx', path)}
                                    ]
                                })
                                newTexRecords[newTexRecord.getName()] = newTexRecord
                                texPaths.append(path)
                                
                            newTexNums.append(texPaths.index(path)+1)

                    newVTEX = Subrecord({'tag':'VTEX', 'data':pack('<256H', *newTexNums)})
                    landRecord.setSubrecord(newVTEX)
                    
        if landRecord:
            newLandRecords[coords] = landRecord  

    masters.update(newMasters)
            
    if len(newLandRecords) <= 0:
        return 'The heightmap was not altered. No plugin will be generated.'
    else:
        if len(newTexRecords) > 0:
            newRecords['LTEX'] = newTexRecords
        
        newRecords['LAND'] = newLandRecords
        
        recordCount = 0
        for recordTag, recordDict in newRecords.items():
            recordCount += len(recordDict)

        headerRecord = Record({
            'tag':'TES3',
            'flags':0,
            'subrecords':[{'tag':'HEDR', 'data':pack('<fI32s256sI', version, 0, '', '', recordCount)}]
        })

        for master in masters:
            size = masters[master]
            headerRecord.addSubrecord({'tag':'MAST', 'data':pack('<' + str(len(master) + 1) + 's', master)})
            headerRecord.addSubrecord({'tag':'DATA', 'data':pack('<Q', size)})

        newRecords['TES3']['0'] = headerRecord

        with open(pluginPath, mode='wb') as f:
            for recordTag in newRecords:
                for recordName in newRecords[recordTag]:
                    record = newRecords[recordTag][recordName]
                    f.write(record.pack())

        return 'Created new plugin at "' + pluginPath + '"'
            
def verifyPath(path):
    directory = ''
    filename = False
    extension = ''
    if path:
        path = path.replace('\\', '/').replace('"', '')
        if os.path.isfile(path):
            filename = os.path.basename(path)
            extension = os.path.splitext(path)[1].lower()
            directory = os.path.dirname(path)
        elif os.path.exists(path):
            directory = path
        else:
            path = False
    return [path, directory, filename, extension]

def openMWPlugins(cfgpath):
    dataFolders = []
    contentFiles = {}
    
    with open(cfgpath, mode='r') as cfg:
        for line in cfg:
            line = line.strip()
            splitLine = line.split('=')
            if len(line) == 0 or line[0] == '#' or len(splitLine) != 2:
                continue
            if splitLine[0].lower() == 'data':
                path = verifyPath(splitLine[1])
                if path and not path[2]:
                    dataFolders.append(path[1])
            elif splitLine[0].lower() == 'content':
                if os.path.splitext(splitLine[1].lower())[1] in ['.esp', '.esm', '.omwaddon']:
                    contentFiles[splitLine[1].lower()] = ''

    for dataPath in dataFolders:
        for item in os.listdir(dataPath):
            if item.lower() in contentFiles:
                contentFiles[item.lower()] = dataPath + '/' + item

    for file, path in contentFiles.copy().items():
        if path == '':
            del contentFiles[file]

    if len(contentFiles) > 0:
        return contentFiles
    else:
        return False

def MWPlugins(inipath):
    masters = {}
    plugins = {}
    contentFiles = {}
    masterDates = {}
    pluginDates = {}
    dataPath = os.path.dirname(inipath) + '/Data Files/'
    
    with open(inipath, mode='r') as ini:
        for line in ini:
            line = line.strip()
            splitLine = line.split('=')
            if len(line) == 0 or line[0] == ';' or len(splitLine) != 2:
                continue
            if splitLine[0].lower()[:8] == 'gamefile':
                path = verifyPath(dataPath + splitLine[1])
                
                if path and path[2]:
                    time = os.path.getmtime(path[0])
                    if path[3] == '.esm':
                        masters[path[2].lower()] = path[0]
                        masterDates[path[2].lower()] = time
                    elif path[3] == '.esp':
                        plugins[path[2].lower()] = path[0]
                        pluginDates[path[2].lower()] = time

    masterDates = {k: v for k, v in sorted(masterDates.items(), key=lambda item: item[1])}
    pluginDates = {k: v for k, v in sorted(pluginDates.items(), key=lambda item: item[1])}

    for name in masterDates:
        contentFiles[name] = masters[name]
    for name in pluginDates:
        contentFiles[name] = plugins[name]

    if len(contentFiles) > 0:
        return contentFiles
    else:
        return False       

def main(argv):
    print('')
    
    response = 'Usage: WNAMtool.py --extract -i <input plugin, openmw.cfg, or morrowind.ini path> -b [bmp output dir]\n                   --repack  -i <input plugin, openmw.cfg, or morrowind.ini path> -b <bmp image path> -o [output plugin path]\n       Arguments in brackets [] are optional.'

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
        if i[2]:
            contentFiles = None
            if i[3] in ['.esp', '.esm', '.omwaddon']:
                contentFiles = {i[2].lower():i[0]}
            elif i[3] == '.cfg':
                contentFiles = openMWPlugins(i[0])
            elif i[3] == '.ini':
                contentFiles = MWPlugins(i[0])
            if contentFiles:
                response = pluginsToBMP(contentFiles, b[1])
        
    elif d['mode'] == '--repack':
        if i[2] and b[3] == '.bmp':
            outputPath = 'WNAM_Falsified.esp'
            if o[3] in ['.esp', '.esm', '.omwaddon']:
                outputPath = o[0]
            elif o[0]:
                outputPath = o[1] + '/' + outputPath
            contentFiles = None
            if i[3] in ['.esp', '.esm', '.omwaddon']:
                contentFiles = {i[2].lower():i[0]}
            elif i[3] == '.cfg':
                contentFiles = openMWPlugins(i[0])
            elif i[3] == '.ini':
                contentFiles = MWPlugins(i[0])
            if contentFiles:
                for name, path in contentFiles.items():
                    if path == o[0]:
                        del contentFiles[name]
                        break
                response = BMPToPlugin(contentFiles, b[0], outputPath)
            
    print(response)

main(sys.argv[1:])
