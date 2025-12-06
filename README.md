# TES3 WNAM Falsifier

This is a Python script for directly editing the 9x9 heightmaps (WNAM) of landscape records (LAND) in Morrowind plugins. This allows for customizing the global map.

[Pillow](https://pillow.readthedocs.io/en/stable/) must be installed in order to use this script.

```
Usage: WNAMtool.py extract -i <input plugin, openmw.cfg, or morrowind.ini path> -b [image output dir] [optional arguments]
                   repack  -i <input plugin, openmw.cfg, or morrowind.ini path> -b <image image path> -o [output plugin path] [optional arguments]
Optional arguments:
       --color       # Applies to repacking; if set, WNAMS will be generated using a colored image instead of a greyscale heightmap.
       --lut <path>  # Applies to extracting and repacking; if a path is specified, a LUT will be read from or written to that location depending on the mode.
       --nocells     # Applies to repacking; if not set, CELL records will be created for corresponding LANDs if they don't already exist.
       --esm         # Applies to extracting and repacking; will only read from/output master files. Used for compatibility with unmodified Morrowind.exe.
       --keepspec    # Applies to repacking; by default, VNML/VHGT are left out when possible, violating the plugin format. Set this to keep them in.
       Arguments with parameters in brackets [] are also optional.
```

## Extracting
You can extract the heightmaps for each landscape record in a given plugin or load order of plugins as a composite image.

To do this, you need to provide the path of the plugin/load order of plugins you're extracting from.

The name of this image will determine its positioning on the global map when repacking, so you shouldn't change it.

## Repacking
You can convert an extracted image into a new plugin that will modify the heightmaps of changed cells.

To do this, you need to provide the plugin(s) with heightmaps you want to overwrite and the path of the image.

The base plugin(s) are needed because it is impossible to only change the heightmap with a plugin. Other things like actual land geometry, texturing, and vertex colors are included in the LAND record as well. Land records will only be included for cells that have actually been changed in the provided image. Any necessary land textures from the base plugins will be included as well.

## Color and LUTs
If the --color argument is set, this script can use colored images instead of heightmaps to generate WNAMs. The image must still have the correct dimensions and be named according to its cell positioning.

If no LUT is provided, one will be automatically generated from the image. Pixels with alpha of 255 will be treated as land, and pixels with alpha below that will be treated as water. A pixel with 0 alpha will have its color used as the lowest value, i.e. the color of empty cells. The land and water palettes can each have 128 unique colors.

If a LUT is provided when extracting a WNAM map, it will be used to color the resulting image.


#### Credits
Author - Qlonever
