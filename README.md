# TES3 WNAM Falsifier

This is a Python script for directly editing the 9x9 heightmaps (WNAM) of landscape records (LAND) in Morrowind plugins. This allows for customizing the global map.

```
Usage: WNAMtool.py extract -i <input plugin, openmw.cfg, or morrowind.ini path> -b [bmp output dir] [optional arguments]
                   repack  -i <input plugin, openmw.cfg, or morrowind.ini path> -b <bmp image path> -o [output plugin path] [optional arguments]
Optional arguments:
       [--nocells]:  Applies to repacking; if not set, CELL records will be created for corresponding LANDs if they don't already exist.
       [--esm]:      Applies to extracting and repacking; will only read from/output master files. Used for compatibility with unmodified Morrowind.exe.
       [--keepspec]: Applies to repacking; by default, VNML/VHGT are left out when possible, violating the plugin format. Set this to keep them in.
       Arguments with parameters in brackets [] are also optional.
```

## Extracting
You can extract the heightmaps for each landscape record in a given plugin or load order of plugins as a composite BMP image.

To do this, you need to provide the path of the plugin/load order of plugins you're extracting from, as well as the directory that the image will be saved in.

The name of this image will determine its positioning on the global map when repacking, so you shouldn't change it.

## Repacking
You can convert an extracted BMP image into a new plugin that will modify the heightmaps of changed cells.

To do this, you need to provide the plugin(s) with heightmaps you want to change, the destination path for the new plugin, and the path of the image.

Note that heightmaps can only be extracted from 8bpp paletted BMPs. After editing the image, you must save it in that format. Paint.NET and GIMP work for this.

The base plugin(s) are needed because it is impossible to only change the heightmap with a plugin. Other things like actual land geometry, texturing, and vertex colors are included in the LAND record as well. Land records will only be included for cells that have actually been changed in the provided image. Any necessary land textures from the base plugins will be included as well.



#### Credits
Author - Qlonever
