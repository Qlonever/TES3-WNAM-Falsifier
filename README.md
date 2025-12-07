# TES3 WNAM Falsifier

This is a Python script for directly editing the 9x9 heightmaps (WNAM) of landscape records (LAND) in Morrowind plugins. This allows for customizing the global map.

[Pillow](https://pillow.readthedocs.io/en/stable/) must be installed in order to use this script.

```
Usage: WNAMtool.py extract -i input plugin path> [--img <dir>] [options]'
                   repack  --img <image path> [-i <input plugin path>] [-o <output plugin path>] [options]'
Options:
        --opt <args>      | Mode | Description
-------------------------------------------------------------------
         -i <path>        | E/R  | The path to a plugin with WNAMs to be extracted/overwritten, or a plugin list (Morrowind.ini/openmw.cfg)
         -o <path>        |  R   | The path to output a plugin to.
        --img <dir/path>  | E/R  | In extract/repack mode, a map image will be written to/read from the given dir/path.
        --lut <path>      | E/R  | A LUT will be read from or written to the specified path depending on the mode.
        --color           |  R   | If set, the input image will be treated as a colored map instead of a greyscale heightmap.
        --esm             | E/R  | If set, only master files will be read/generated. Used for compatibility with unmodified Morrowind.exe.'
        --nocells         |  R   | If set, CELL records won\'t be generated for terrain squares that lack them.
        --keepspec        |  R   | If set, generated LAND records will include VNML/VHGT. This is almost never necessary.
```

## Extracting
You can extract the heightmaps for each landscape record in a given plugin or load order of plugins as a composite image.

To do this, you need to provide the path of the plugin you're extracting from, or a Morrowind.ini/openmw.cfg file containing a list of plugins.

The name of the generated image will determine its positioning on the global map when repacking, so you shouldn't change it.

## Repacking
You can convert an image into a new plugin that will modify the heightmaps of changed cells.

To do this, you need to provide the path of the image, as well as any plugin(s) with heightmaps you want to overwrite. The image should be named according to the coordinate of the bottom-leftmost cell it represents. (x,y)

The base plugin(s) are needed because it is impossible to only change the heightmap with a plugin. Other things like actual land geometry, texturing, and vertex colors are included in the LAND record as well. Land records will only be included for cells that have actually been changed in the provided image. Any necessary land textures from the base plugins will be included as well.

## Color and LUTs
If the --color argument is set, this script can use colored images instead of heightmaps to generate WNAMs. The image must still have the correct dimensions and be named according to its cell positioning.

If no LUT is provided, one will be automatically generated from the image. Pixels with alpha of 255 will be treated as land, and pixels with alpha below that will be treated as water. A pixel with 0 alpha will have its color used as the lowest value, i.e. the color of empty cells. The land and water palettes can each have 128 unique colors.

If a LUT is provided when extracting a WNAM map, it will be used to color the resulting image.


#### Credits
Author - Qlonever
