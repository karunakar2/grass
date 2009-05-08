#!/usr/bin/env python

############################################################################
#
# MODULE:       r.in.wms
#
# AUTHOR(S):    Cedric Shock, 2006
#               Pythonized by Martin Landa <landa.martin gmail.com>, 2009
#
# PURPOSE:      To import data from web mapping servers
#               (based on Bash script by Cedric Shock)
#
# COPYRIGHT:    (C) 2009 Martin Landa, and GRASS development team
#
#               This program is free software under the GNU General
#               Public License (>=v2). Read the file COPYING that
#               comes with GRASS for details.
#
#############################################################################

import os
import glob
import grass

class WMSRequest:
    def __init__(self, flags, options):
        self.flags   = flags
        self.options = options

        self.__set_options()
        
    def __set_options(self):
        # If the user asserts that this projection is the same as the
        # source use this projection as the source to get a trivial
        # tiling from r.tileset
        if self.flags['p']:
            self.proj_srs = grass.read_command('g.proj', flags='j')
            self.srs_scale = int(grass.parse_key_val(proj_srs['+to_meter']))
        else:
            self.proj_srs = '+init=%s' % self.options['srs'].lower()
            self.srs_scale = 1

        # options for r.tileset
        self.tileset_options = grass.parse_key_val(self.options['tileoptions'])
        if self.options['region']:
            self.tileset_options['region'] = self.options['region']
        
        # set transparency
        if self.flags['o']:
            self.transparency = "transparent=FALSE"
        else:
            self.transparency = "transparent=FALSE"

        # image format
        format_opt = self.options['format']
        if format_opt == "geotiff":
            self.format      = "image/geotiff"
            self.worldfile   = ".tfw"
            self.file_extent = ".geotiff"
        elif format_opt == "tiff":
            self.format      = "image/tiff"
            self.worldfile   = ".tfw"
            self.file_extent = ".tiff"
        elif format_opt == "png":
            self.format      = "image/png"
            self.worldfile   = ".pgw"
            self.file_extent = ".png"
        elif format_opt == "jpeg":
            self.format      = "image/jpeg"
            self.worldfile   = ".jgw"
            self.file_extent = ".jpeg"
        elif format_opt == "gif":
            self.format      = "image/gif"
            self.worldfile   = ".gfw"
            self.file_extent = ".gif"
        else:
            grass.fatal("Uknown image format '%s'" % format_opt)

        # create download directory
        if not os.path.exists(self.options['folder']):
            os.mkdir(self.options['folder'])
        
        # clean files
        self._tdir = os.path.join(self.options['folder'], self.options['output'],
                            self.options['region'])

        self.request_file = os.path.join(self._tdir, 'request')

    def GetRequestFile(self):
        return self.request_file
    
    def GetRequests(self):
        ret = []
        rf = open(self.request_file)
        try:
            for line in rf.readlines():
                ret.append(grass.parse_key_val(line, vsep = ';'))
        finally:
            rf.close()

        return ret

    def GetTiles(self):
        grass.message("Calculating tiles...")
        tiles = grass.read_command('r.tileset',
                                quiet = True,
                                flags = 'g',
                                sourceproj = self.proj_srs,
                                sourcescale = self.srs_scale,
                                overlap = 2,
                                maxcols = int(self.options['maxcols']),
                                maxrows = int(self.options['maxrows']),
                                **self.tileset_options)
        if not tiles:
            grass.fatal("r.tileset failed")
        tiles = tiles.splitlines()
        grass.message("Requesting %d tiles" % len(tiles))
        
        if self.flags['c']:
            rmfiles = os.path.join(self._tdir, '*')
            grass.verbose("Removing files '%s'" % rmfiles)
            for file in glob.glob(rmfiles):
                if os.path.isdir(file):
                    os.rmdir(file)
                else:
                    os.remove(file)

        rf = open(self.request_file, 'w')
        i = 0
        for tile in tiles:
            outputfile = os.path.join(self._tdir, str(i) + self.file_extent)
            worldfile = os.path.join(self._tdir, str(i) + self.worldfile)
            dtile = grass.parse_key_val(tile, vsep=';')
            n = float(dtile['n'])
            s = float(dtile['s'])
            e = float(dtile['e'])
            w = float(dtile['w'])
            nr = int(dtile['rows'])
            nc = int(dtile['cols'])

            size = "bbox=%f,%f,%f,%f&width=%d&height=%d" % \
                (w, s, e, n, nr, nc)
            xres = (e - w) / nc
            yres = (s - n) / nr
            # center of top left cell
            top_left_cell_center_x = w + xres / 2
            top_left_cell_center_y = n + yres / 2

            # write the world file
            wf = open(worldfile, 'w')
            try:
                wf.write("%f\n0.0\n0.0\n%f\n%f\n%f\n" % \
                             (xres, yres, top_left_cell_center_x, top_left_cell_center_y))
            finally:
                wf.close()

            # request for data
            string = "request=GetMap&layers=%s&srs=%s&%s&format=%s&%s&%s" % \
                (self.options['layers'], self.options['srs'],
                 size, self.format, self.transparency, self.options['wmsquery'])
            if self.options['styles']:
                string += "&styles=%s" % self.options['styles']
            rf.write('output=%s;server=%s;string=%s\n' % \
                         (outputfile, self.options['mapserver'], string))
            i += 1
        
        rf.close()
