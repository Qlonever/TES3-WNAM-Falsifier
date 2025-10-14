import math
import struct
import os
import sys
import getopt

# Automatically convert i/o strings/bytes to bytes/strings
# Allow variable string length
def pack(*args):
    args = list(args)
    fmt = list(args.pop(0))
    f = 0
    for i in range(len(args)):
        arg = args[i]
        if isinstance(arg, str):
            args[i] = arg.encode('ascii')
            f = fmt.index('s', f+1)
            if fmt[f-1] == '#':
                fmt[f-1] = str(len(arg))
    args.insert(0, ''.join(fmt))
    return bytearray(struct.pack(*args))

def unpack(*args):
    args = list(args)
    fmt = list(args[0])
    # Account for 1 string of variable length per byte input
    if '#' in fmt:
        index = fmt.index('#')
        sizeOther = ''.join(fmt[:index] + fmt[index+2:])
        sizeOther = struct.calcsize(sizeOther)
        fmt[index] = str(len(args[1]) - sizeOther)
        args[0] = ''.join(fmt)
    ret = list(struct.unpack(*args))
    for i in range(len(ret)):
        if isinstance(ret[i], bytes):
            ret[i] = ret[i].decode('ascii')
    return tuple(ret)

# Return nearest multiple of pad >= length
def padLength(length, pad):
    return int(pad * math.ceil(length/pad))

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

    def r(self, index):
        return self.value[index][0]
    def g(self, index):
        return self.value[index][1]
    def b(self, index):
        return self.value[index][2]
    def a(self, index):
        return self.value[index][3]
    def rgba(self, index):
        return self.value[index]

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
            return None

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
                    return True
                count += 1
        return False

    def delSubrecord(self, tag, index=0):
        count = 0
        for i in range(len(self.subrecords)):
            subrecord = self.subrecords[i]
            if subrecord.tag == tag:
                if count == index:
                    del self.subrecords[i]
                    del self.subrecordsSorted[tag][count]
                    if len(self.subrecordsSorted[tag]) <= 0:
                        del self.subrecordsSorted[tag]
                    return True
                count += 1
        return False

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


######## BMP/image handling ########


heightPalette = []
for i in range(128, 256):
    heightPalette.append([i, i, i, 0])
for i in range(128):
    heightPalette.append([i, i, i, 0])
heightPalette = ColorTable(heightPalette)

baseBMPheader = {
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

def parseBMPHeader(f):
    offset = 0
    header = {}
    for itemName, item in baseBMPheader.items():
        itemFormat = item['format']
        default = item['value']
        size = struct.calcsize(itemFormat)
        itemBytes = f.read(size)
        data, = unpack(itemFormat, itemBytes)

        if data != default and 'error' in item:
            print(header[item]['error'])
            return False

        header[itemName] = {'format':itemFormat, 'value':data}
        offset += size
    return header

def WNAMsFromBMP(bmpPath, coords):
    pixelArray = None
    with open(bmpPath, mode='rb') as img:
        header = parseBMPHeader(img)
        if not header:
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
        # Image editors cannot be relied upon to preserve color tables
        for pixel in pixelData:
            red = palette.r(pixel)
            if red >= 128:
                red -= 128
            else:
                red += 128
            b.append(red)
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
    for itemName, item in baseBMPheader.items():
        itemFormat = item['format']
        value = item['value']
        if itemName == 'FileSize':
            value = 0x436 + pixelArray.height * pixelArray.padWidth
        elif itemName == 'Width':
            value = pixelArray.width
        elif itemName == 'Height':
            value = pixelArray.height
        elif itemName == 'ImageSize':
            value = pixelArray.height * pixelArray.padWidth
        b += pack(itemFormat, value)
    b += heightPalette.to_bytes()
    b += pixelArray.value
    with open(bmpPath, mode='wb') as img:
        img.write(b)


######## Plugin/record handling ########
        

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

# Takes records as dictionary:
# {
#   'TAG':[Record, ...],
#   ...
# {
def writePlugin(pluginPath, records):
    with open(pluginPath, mode='wb') as f:
        for recordTag in records:
            for recordName in records[recordTag]:
                record = records[recordTag][recordName]
                f.write(record.pack())

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
            record.setSubrecord(defaultLAND.getSubrecord('VNML'))
            record.setSubrecord(defaultLAND.getSubrecord('VHGT'))
            record.setSubrecord(defaultLAND.getSubrecord('WNAM'))
            records[coords] = record
    return records


######## Main mode functions ########


def pluginsToBMP(pluginList, bmpDir):
    landRecords = recordsFromPlugins(pluginList, ['LAND'])['LAND']
    landRecords = sanitizeLand(landRecords)
    if len(landRecords) <= 0:
        return 'Couldn\'t find any LAND records in the provided plugin(s).'

    # Calculate bounding rectangle surrounding all LANDs
    left = right = top = bottom = None
    for coords in landRecords:
        coords = coords.split(',')
        x = int(coords[0])
        y = int(coords[1])
        left = min(x, left or x)
        right = max(x, right or x)
        bottom = min(y, bottom or y)
        top = max(y, top or y)

    # Actual width/height are 1 more than bounding dimensions
    cellWidth = right - left + 1
    cellHeight = top - bottom + 1
    
    width = cellWidth * 9
    height = cellHeight * 9
    padWidth = padLength(width, 4)

    # Initialize image as seafloor value, which is -128
    mapArray = (pack('<b', -128) * width + bytearray(padWidth-width)) * height
    mapArray = PixelArray(mapArray, width, height, padWidth)
    
    for x in range(cellWidth):
        worldX = x + left
        for y in range(cellHeight):
            worldY = y + bottom
            key = str(worldX) + ',' + str(worldY)
            b = None
            if key in landRecords:
                b = landRecords[key].getSubrecord('WNAM').data
                cellArray = PixelArray(b, 9, 9, 9)
                mapArray.impose(cellArray, x*9, y*9)
    if bmpDir:
        bmpDir += '/'
    bmpPath = bmpDir + str(left) + ',' + str(bottom) + '.bmp'
    BMPFromPixelArray(bmpPath, mapArray)
    return 'Converted ' + str(len(landRecords)) + ' WNAMs to BMP at "' + bmpPath + '"'

def BMPToPlugin(mastersDict, bmpPath, pluginPath, noCells=False, keepSpec=False):
    # Leaving these out is technically wrong but doesn't cause any problems
    if not keepSpec:
        defaultLAND.delSubrecord('VNML')
        defaultLAND.delSubrecord('VHGT')
        
    baseCoords = os.path.splitext(os.path.basename(bmpPath))[0].split(',')
    x = None
    y = None
    try:
        x = int(baseCoords[0])
        y = int(baseCoords[1])
    except:
        return 'The image isn\'t named according to a cell coordinate. [x,y]'
    
    imageWNAMs = WNAMsFromBMP(bmpPath, (x,y))
    
    oldRecords = recordsFromPlugins(mastersDict, ['TES3', 'LAND', 'LTEX'])
    newRecords = {'TES3':{}, 'LTEX':{}, 'LAND':{}, 'CELL':{}}
    
    oldLandRecords = sanitizeLand(oldRecords['LAND'])
    oldTexRecords = oldRecords['LTEX']
    texPaths = []

    version, = unpack('<f', pack('<f', 1.2))
    # Use capitalized filenames here so MAST subrecords will match plugins used
    # Use lowercase names elsewhere since plugins overwrite each other case-insensitively
    masters = {
        'Morrowind.esm':79837557
    }
    newMasters = {}

    for coords, imageWNAM in imageWNAMs.items():
        landRecord = None
        # New landscapes not from plugins
        if not coords in oldLandRecords:
            if imageWNAM.data != pack('<b', -128) * 81:
                x, y = coords.split(',')
                coordSubrecord = Subrecord({'tag':'INTV', 'data':pack('<2i', int(x), int(y))})
                landRecord = Record({
                    'tag':'LAND',
                    'flags':0,
                    'subrecords':[
                        coordSubrecord,
                        defaultLAND.getSubrecord('DATA'),
                        defaultLAND.getSubrecord('VNML'),
                        defaultLAND.getSubrecord('VHGT'),
                        imageWNAM
                    ]
                })

                # Morrowind.exe won't display WNAMs for grid squares without CELL records
                # OpenMW won't expand the map for grid squares without CELL records
                # However, including these prevents automatic fish spawning
                if not noCells:
                    cellName = Subrecord({'tag':'NAME', 'data':bytearray(1)})
                    cellData = Subrecord({'tag':'DATA', 'data':pack('<I2i', 2, int(x), int(y))})
                    newRecords['CELL'][coords] = Record({
                        'tag':'CELL',
                        'flags':0,
                        'subrecords':[
                            cellName,
                            cellData
                        ]
                    })

        # Pre-existing landscapes from plugins
        else:
            oldLandRecord = oldLandRecords[coords]
            oldWNAM = oldLandRecord.getSubrecord('WNAM')
            if oldWNAM.data != imageWNAM.data:
                landRecord = oldLandRecord
                landRecord.setSubrecord(imageWNAM)
                
                # Add dependencies for plugins whose WNAMs were changed
                # Base game/expansion dependencies are added automatically
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

                # Handle land textures
                oldVTEX = landRecord.getSubrecord('VTEX')
                if oldVTEX:
                    newTexNums = []
                    oldTexNums = list(unpack('<256H', oldVTEX.data))
                    for index in oldTexNums:
                        # Beware, VTEX indices are +1 from LTEX indices
                        # Index 0 always denotes default land texture
                        if index == 0:
                            newTexNums.append(0)
                        else:
                            oldTexRecord = oldTexRecords[masterName + ' ' + str(index - 1)]
                            path = oldTexRecord.getSubrecord('DATA').data
                            path, = unpack('<#sx', path)
                            # Only keep one LTEX for each land texture, even if it exists in multiple plugins
                            if not path in texPaths:
                                newTexRecord = Record({
                                    'tag':'LTEX',
                                    'flags':0,
                                    'subrecords':[
                                        # Things break if LTEX don't have unique names
                                        {'tag':'NAME', 'data':pack('<4sx', str(len(texPaths)).zfill(4))},
                                        {'tag':'INTV', 'data':pack('<I', len(texPaths))},
                                        {'tag':'DATA', 'data':pack('<' + str(len(path)) + 'sx', path)}
                                    ]
                                })
                                newRecords['LTEX'][newTexRecord.getName()] = newTexRecord
                                texPaths.append(path)
                                
                            newTexNums.append(texPaths.index(path)+1)

                    newVTEX = Subrecord({'tag':'VTEX', 'data':pack('<256H', *newTexNums)})
                    landRecord.setSubrecord(newVTEX)
                    
        if landRecord:
            newRecords['LAND'][coords] = landRecord  

    # Do this here so Tribunal/Bloodmoon dependencies come immediately after Morrowind.esm
    masters.update(newMasters)

    numChanged = len(newRecords['LAND'])
    if numChanged <= 0:
        return 'The heightmap was not altered. No plugin will be generated.'
    else: 
        recordCount = 0
        for recordTag, recordDict in newRecords.items():
            recordCount += len(recordDict)

        headerRecord = Record({
            'tag':'TES3',
            'flags':0,
            # Consider adding command-line option for setting version/author/description
            'subrecords':[{'tag':'HEDR', 'data':pack('<fI32s256sI', version, 0, '', '', recordCount)}]
        })

        for master in masters:
            size = masters[master]
            headerRecord.addSubrecord({'tag':'MAST', 'data':pack('<#sx', master)})
            headerRecord.addSubrecord({'tag':'DATA', 'data':pack('<Q', size)})

        newRecords['TES3']['0'] = headerRecord

        writePlugin(pluginPath, newRecords)

        return 'Generated WNAMs for ' + str(numChanged) + ' cells.\nCreated new plugin at "' + pluginPath + '"'


######## User input ########


def verifyPath(path, fileShouldExist=True):
    directory = ''
    filename = False
    extension = ''
    if path:
        path = path.strip().replace('\\', '/').replace('"', '')
        splitPath = os.path.split(path)
        splitName = os.path.splitext(splitPath[1])
        if os.path.isdir(path):
            directory = path
        elif os.path.isdir(splitPath[0]) and splitName[1]:
            directory = splitPath[0]
            if (not fileShouldExist) or os.path.isfile(path):
                filename = splitPath[1]
                extension = splitName[1]
        else:
            path = False
    return [path, directory, filename, extension]     

def openMWPlugins(cfgpath, esmOnly=False):
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
                validExtensions = ['.esm']
                if not esmOnly:
                    validExtensions += ['.esp', '.omwaddon']
                if os.path.splitext(splitLine[1].lower())[1] in validExtensions:
                    # Store lowercase plugin names since plugins overwrite each other case-insensitively
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

def MWPlugins(inipath, esmOnly=False):
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
    if not esmOnly:
        for name in pluginDates:
            contentFiles[name] = plugins[name]

    if len(contentFiles) > 0:
        return contentFiles
    else:
        return False       

def main(argv):
    print('')
    
    response =    'Usage: WNAMtool.py extract -i <input plugin, openmw.cfg, or morrowind.ini path> -b [bmp output dir] [optional arguments]'
    response += '\n                   repack  -i <input plugin, openmw.cfg, or morrowind.ini path> -b <bmp image path> -o [output plugin path] [optional arguments]'
    response += '\nOptional arguments:'
    response += '\n       [--nocells]:  Applies to repacking; if not set, CELL records will be created for corresponding LANDs if they don\'t already exist.'
    response += '\n       [--esm]:      Applies to extracting and repacking; will only read from/output master files. Used for compatibility with unmodified Morrowind.exe.'
    response += '\n       [--keepspec]: Applies to repacking; by default, VNML/VHGT are left out when possible, violating the plugin format. Set this to keep them in.'
    response += '\n       Arguments with parameters in brackets [] are also optional.'

    opts, args = getopt.gnu_getopt(argv, 'i:b:o:', longopts=['nocells', 'esm', 'keepspec'])
    d = {
        'mode':False,
        '-i':False,
        '-b':False,
        '-o':False
    }
    for opt, arg in opts:
        d[opt] = arg

    for arg in args:
        if arg in ['extract', 'repack']:
            d['mode'] = arg

    i = verifyPath(d['-i'], True)
    b = verifyPath(d['-b'], d['mode'] == 'repack')
    o = verifyPath(d['-o'])

    contentFiles = None
    if i[3] in ['.esp', '.esm', '.omwaddon']:
        contentFiles = {i[2].lower():i[0]}
    elif i[3] == '.cfg':
        contentFiles = openMWPlugins(i[0], '--esm' in d)
    elif i[3] == '.ini':
        contentFiles = MWPlugins(i[0], '--esm' in d)
    
    if d['mode'] == 'extract' and contentFiles:
        response = pluginsToBMP(contentFiles, b[1])
        
    elif d['mode'] == 'repack' and contentFiles:
        for name, path in contentFiles.items():
            if path == o[0]:
                del contentFiles[name]
                break
        if len(contentFiles) > 0 and b[3] == '.bmp':
            outputPath = 'WNAM_Falsified.esp'
            if '--esm' in d:
                outputPath = 'WNAM_Falsified.esm'
            if o[3] in ['.esp', '.esm', '.omwaddon']:
                outputPath = o[0]
            elif o[0]:
                outputPath = o[1] + '/' + outputPath
            response = BMPToPlugin(contentFiles, b[0], outputPath, '--nocells' in d, '--keepspec' in d)
            
    print(response)

main(sys.argv[1:])
