# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os, time

from urlparse import urlparse

from xl import common
from xl.media import flac, mp3, mp4, mpc, ogg, tta, wav, wma, wv

from mutagen.mp3 import HeaderNotFoundError
from storm.locals import *

import logging
logger = logging.getLogger(__name__)

# map file extensions to tag modules
formats = {
    'aac': mp4,
    'ac3': None,
    'flac': flac,
    'm4a': mp4,
    'mp+': mpc,
    'mp2': mp3,
    'mp3': mp3,
    'mp4': mp4,
    'mod': None,
    'mpc': mpc,
    'oga': ogg,
    'ogg': ogg,
    's3m': None,
    'tta': tta,
    'wav': wav,
    'wma': wma,
    'wv': wv,
}

SUPPORTED_MEDIA = ['.' + ext for ext in formats.iterkeys()]

def lstrip_special(field):
    """
        Strip special chars off the beginning of a field for sorting. If
        stripping the chars leaves nothing the original field is returned with
        only whitespace removed.
    """
    lowered = field.lower()
    stripped = lowered.lstrip(" `~!@#$%^&*()_+-={}|[]\\\";'<>?,./")
    if stripped:
        return stripped
    return lowered.lstrip()

class Track(object):
    """
        Represents a single track.
    """
    __storm_table__ = "tracks"
    id = Int(primary=True)
    title = Unicode()
    version = Unicode()
    album = Unicode()
    tracknumber = Unicode()
    artist = Unicode()
    genre = Unicode()
    performer = Unicode()
    copyright = Unicode()
    license = Unicode()
    organization = Unicode()
    description = Unicode()
    location = Unicode()
    contact = Unicode()
    isrc = Unicode()
    date = Unicode()
    arranger = Unicode()
    author = Unicode()
    composer = Unicode()
    conductor = Unicode()
    lyricist = Unicode()
    discnumber = Unicode()
    labelid = Unicode()
    part = Unicode()
    website = Unicode()
    language = Unicode()
    encodedby = Unicode()
    bpm = Unicode()
    albumartist = Unicode()
    originaldate = Unicode()
    originalalbum = Unicode()
    originalartist = Unicode()
    recordingdate = Unicode()
    playcount = Int()
    bitrate = Int()
    length = Float()
    blacklisted = Bool()
    rating = Float()
    loc = Unicode()
    encoding = Unicode()
    modified = Int()

    def __init__(self, uri=None):
        """
            loads and initializes the tag information
            
            uri: path to the track [string]
            _unpickles: unpickle data [tuple] # internal use only!
        """

        self._scan_valid = False
        if uri:
            self.set_loc(uri)
            if self.read_tags() is not None:
                self._scan_valid = True

    def set_loc(self, loc):
        """
            Sets the location. It is always in unicode.

            If the value is not unicode, convert it into unicode using some
            default mapping. This way, when we want to access the file, we
            decode it back into the ascii and don't worry about botched up
            characters (ie the value should be exactly identical to the 
            one given)

            loc: the location [string]
        """
        loc = common.to_unicode(loc, 
                common.get_default_encoding())
        if loc.startswith("file://"):
            loc = loc[7:]
        self.loc = loc
       
    def get_loc(self):
        """
            Gets the location as unicode (might contain garbled characters)

            returns: the location [string]
        """
        return self.loc

    def get_loc_for_io(self):
        """
            Gets the location as ascii. Should always be correct, see 
            set_loc.

            returns: the location [string]
        """
        return self.loc.encode(common.get_default_encoding())

    def get_tag(self, tag):
        """
            Common function for getting a tag.
            
            tag: tag to get [string]
        """
        try:
            values = getattr(self, tag)
            if u'\x00' in values:
                values = values.split(u'\x00')
            return values
        except:
            return None

    def set_tag(self, tag, values, append=False, emit=True):
        """
            Common function for setting a tag.
            
            tag: tag to set [string]
            values: list of values for the tag [list]
            append: whether to append to existing values [bool]
        """

        #if tag in common.VALID_TAGS:
        #    values = [values]
        if not isinstance(values, list):
            if append:
                values = [values]
            else:
                if type(values) == str:
                    values = unicode(values)
                setattr(self, tag, values)

        # filter out empty values and convert to unicode
        if isinstance(values, list):
            values = [common.to_unicode(x, self.encoding) for x in values
                if x not in (None, '')]
            if append:
                values = self.get_tag(tag).extend(values)
                setattr(self, tag, u'\x00'.join(values))
            else:
                setattr(self, tag, u'\x00'.join(values))
        
    def __getitem__(self, tag):
        """
            Allows retrieval of tags via Track[tag] syntax.
            Returns a list of values for the tag, even for single values.
        """
        return self.get_tag(tag)

    def __setitem__(self, tag, values):
        """
            Allows setting of tags via Track[tag] syntax.
            Expects a list of values, even for single values.

            Use set_tag if you want to do appending instead of
            always overwriting.
        """
        self.set_tag(tag, values, False)

    def write_tags(self):
        """
            Writes tags to file
        """
        (path, ext) = os.path.splitext(self.get_loc().lower())
        ext = ext[1:]

        if not formats.get(ext):
            logger.info("Writing metadata to type '%s' is not supported" % 
                    ext)
        else:
            formats[ext].write_tag(self)

    def read_tags(self):
        """
            Reads tags from file
        """
        if urlparse(self.get_loc())[0] != "":
            return None #not a local file
        (path, ext) = os.path.splitext(self.get_loc().lower())
        ext = ext[1:]

        if ext not in formats:
            logger.debug('%s format is not understood' % ext)
            return None

        format = formats.get(ext)
        if not format: 
            return None

        try:
            self['modified'] = os.path.getmtime(self.get_loc_for_io())
        except OSError:
            pass
        try:
            format.fill_tag_from_path(self)
        except HeaderNotFoundError:
            logger.warning("Possibly corrupt file: " + self.get_loc())
            return None
        except:
            common.log_exception(logger)
            return None
        return self

    def get_track(self):
        """
            Gets the track number in int format.  
        """
        t = self.get_tag('tracknumber')
        if t.find('/') > -1:
            t = t[:t.find('/')]
        if t == '':
            t = -1

        return int(t)

    def get_duration(self):
        """
            Returns the length of the track as an int in seconds
        """
        if not self['length']: self['length'] = 0
        return int(float(self['length']))

    def sort_param(self, field):
        """ 
            Returns a sortable of the parameter given (some items should be
            returned as an int instead of unicode)
        """
        if field == 'tracknumber': return self.get_track()
        elif field == 'artist':
            artist = lstrip_special(self['artist'])
            if artist.find('the ') == 0:
                artist = artist[4:]
            return artist
        else: return lstrip_special(self[field])

    def __repr__(self):
        return str(self)

    def __str__(self):
        """
            returns a string representing the track
        """
        title = self['title']
        album = self['album']
        artist = self['artist']
        ret = "'"+title+"'"
        if artist.strip():
            ret += " by '%s'" % artist
        if album.strip():
            ret += " from '%s'" % album
        return ret

# vim: et sts=4 sw=4

