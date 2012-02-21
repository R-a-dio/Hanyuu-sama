import sys

cdef extern from "sys/types.h":
    ctypedef unsigned int size_t
    ctypedef int ssize_t

cdef extern from "shout/shout.h":
    #types
    ctypedef struct shout_t
    ctypedef struct shout_metadata_t

    #methods
    void shout_init()
    void shout_shutdown()
    char *shout_version(int *major, int *minor, int *patch)
    shout_t *shout_new()
    void shout_free(shout_t *self)
    char *shout_get_error(shout_t *self)
    int shout_get_errno(shout_t *self)
    int shout_get_connected(shout_t *self)
    
    int shout_open(shout_t *self)
    int shout_close(shout_t *self)
    int shout_send(shout_t *self, unsigned char *data, size_t len)
    ssize_t shout_send_raw(shout_t *self, unsigned char *data, size_t len)
    ssize_t shout_queuelen(shout_t *self)
    void shout_sync(shout_t *self)
    int shout_delay(shout_t *self)

    #properties:
    int shout_set_host(shout_t *self, char *host)
    char *shout_get_host(shout_t *self)

    int shout_set_port(shout_t *self, unsigned short port)
    unsigned short shout_get_port(shout_t *self)

    int shout_set_user(shout_t *self, char *username)
    char *shout_get_user(shout_t *self)

    int shout_set_password(shout_t *, char *password)
    char *shout_get_password(shout_t *self)

    int shout_set_mount(shout_t *self, char *mount)
    char *shout_get_mount(shout_t *self)

    int shout_set_name(shout_t *self, char *name)
    char *shout_get_name(shout_t *self)

    int shout_set_url(shout_t *self, char *url)
    char *shout_get_url(shout_t *self)

    int shout_set_genre(shout_t *self, char *genre)
    char *shout_get_genre(shout_t *self)

    int shout_set_agent(shout_t *self, char *agent)
    char *shout_get_agent(shout_t *self)

    int shout_set_description(shout_t *self, char *description)
    char *shout_get_description(shout_t *self)

    int shout_set_dumpfile(shout_t *self, char *dumpfile)
    char *shout_get_dumpfile(shout_t *self)

    int shout_set_audio_info(shout_t *self, char *name, char *value)
    char *shout_get_audio_info(shout_t *self, char *name)

    int shout_set_public(shout_t *self, unsigned int make_public)
    unsigned int shout_get_public(shout_t *self)

    int shout_set_metadata(shout_t *self, shout_metadata_t *metadata)
    shout_metadata_t *shout_metadata_new()
    void shout_metadata_free(shout_metadata_t *self)
    int shout_metadata_add(shout_metadata_t *self, char *name, char *value)

    int shout_set_format(shout_t *self, unsigned int format)
    unsigned int shout_get_format(shout_t *self)

    int shout_set_protocol(shout_t *self, unsigned int protocol)
    unsigned int shout_get_protocol(shout_t *self)

    int shout_set_nonblocking(shout_t* self, unsigned int nonblocking)
    unsigned int shout_get_nonblocking(shout_t *self)

#Some constants
SHOUTERR_SUCCES = 1
SHOUTERR_INSANE = -1
SHOUTERR_NOCONNECT = -2
SHOUTERR_NOLOGIN = -3
SHOUTERR_SOCKET = -4
SHOUTERR_MALLOC = -5
SHOUTERR_METADATA = -6
SHOUTERR_CONNECTED = -7
SHOUTERR_UNCONNECTED = -8
SHOUTERR_UNSUPPORTED = -9
SHOUTERR_BUSY = -10

SHOUT_FORMAT_OGG = 0
SHOUT_FORMAT_MP3 = 1
#backward-compatibility alias
SHOUT_FORMAT_VORBIS	= SHOUT_FORMAT_OGG

SHOUT_PROTOCOL_HTTP = 0
SHOUT_PROTOCOL_XAUDIOCAST = 1
SHOUT_PROTOCOL_ICY = 2

SHOUT_AI_BITRATE =  'bitrate'
SHOUT_AI_SAMPLERATE = 'samplerate'
SHOUT_AI_CHANNELS = 'channels'
SHOUT_AI_QUALITY = 'quality'

def version():
    """returns a static version string.  Non-null parameters will be set 
    to theAttributeError: 'PropertyScope' object has no attribute 
    'namespace_cname'"""
    cdef int *major
    cdef int *minor
    cdef int *patch
    return shout_version(major, minor, patch)

class ShoutException(Exception):
    pass

cdef class Shout:
    """Allocates and sets up a new shout_t.  Returns NULL if it can't get 
    enough * memory.  The returns shout_t must be disposed of 
    with shout_free."""
    cdef shout_t *shout_t
    cdef shout_metadata_t *shout_metadata_t
    __audio_info = {}
    __metadata = {}

    def __init__(self):
        """initializes the shout library. Must be called before anything else"""
        shout_init()
        self.shout_t = shout_new()
        self.shout_metadata_t = shout_metadata_new()

    def open(self):
        """shout_open (no switching back and forth midstream at the moment)."""
        i = shout_open(self.shout_t)
        if i != 0:
            raise ShoutException(self.get_errno(), self.get_error())

    def send(self, data):
        i = shout_send(self.shout_t, data, len(data))
        if i != 0:
            raise ShoutException(self.get_errno(), self.get_error())

    def send_raw(self, data):
        """Send unparsed data to the server.  Do not use this unless you 
        know what you are doing. 
        Returns the number of bytes written, or < 0 on error."""
        i = shout_send_raw(self.shout_t, data, len(data))
        if i != 0:
            raise ShoutException(self.get_errno(), self.get_error())

    def queuelen(self):
        """return the number of bytes currently on the write queue (only 
        makes sense in nonblocking mode)"""
        i = shout_queuelen(self.shout_t)
        if i != 0:
            raise ShoutException(self.get_errno(), self.get_error())

    def sync(self):
        """Puts caller to sleep until it is time to send more data to the
        server"""
        shout_sync(self.shout_t)

    def delay(self):
        """Amount of time in ms caller should wait before sending again"""
        i = shout_delay(self.shout_t)
        if i != 0:
            raise ShoutException(self.get_errno(), self.get_error())

    def close(self):
        i = shout_close(self.shout_t)
        if i != 0:
            raise ShoutException(self.get_errno(), self.get_error())

    def get_error(self):
        """Returns a statically allocated string describing the last shout error
         * to occur.  Only valid until the next libshout call on this 
        shout_t"""
        return shout_get_error(self.shout_t)

    def get_errno(self):
        """Return the error code (e.g. SHOUTERR_SOCKET) for this shout 
        instance"""
        return shout_get_errno(self.shout_t)

    def connected(self):
        """returns SHOUTERR_CONNECTED or SHOUTERR_UNCONNECTED"""
        return shout_get_connected(self.shout_t)

    def __del(self):
        self.close()
        shout_shutdown()

    """Parameter manipulation functions.  libshout makes copies of all 
    parameters, the caller may free its copies after giving them to 
    libshout. May return * SHOUTERR_MALLOC */"""
    property host:
        "A doc string can go here."

        def __get__(self):
            "Defaults to localhost"
            return shout_get_host(self.shout_t)

        def __set__(self, host):
            host = str(host)
            i = shout_set_host(self.shout_t, host)
            if i != 0:
                raise ShoutException(i, 'Host is not correct')

    property port:
        "A doc string can go here."

        def __get__(self):
            "Defaults to 8000"
            return shout_get_port(self.shout_t)

        def __set__(self, port):
            port = int(port)
            i = shout_set_port(self.shout_t, port)
            if i != 0:
                raise ShoutException(i, 'Port is not correct')

    property user:
        "A doc string can go here."

        def __get__(self):
            return shout_get_user(self.shout_t)

        def __set__(self, user):
            user = str(user)
            i = shout_set_user(self.shout_t, user)
            if i != 0:
                raise ShoutException(i, 'User is not correct')

    property password:
        "A doc string can go here."

        def __get__(self):
            "Defaults to 8000"
            return shout_get_password(self.shout_t)

        def __set__(self, password):
            password = str(password)
            i = shout_set_password(self.shout_t, password)
            if i != 0:
                raise ShoutException(i, 'password is not correct')

    property mount:
        "A doc string can go here."

        def __get__(self):
            "Defaults to 8000"
            return shout_get_mount(self.shout_t)

        def __set__(self, mount):
            mount = str(mount)
            i = shout_set_mount(self.shout_t, mount)
            if i != 0:
                raise ShoutException(i, 'mount is not correct')

    property name:
        "A doc string can go here."

        def __get__(self):
            return shout_get_name(self.shout_t)

        def __set__(self, name):
            name = str(name)
            i = shout_set_name(self.shout_t, name)
            if i != 0:
                raise ShoutException(i, 'name is not correct')

    property url:
        "A doc string can go here."

        def __get__(self):
            return shout_get_url(self.shout_t)

        def __set__(self, url):
            url = str(url)
            i = shout_set_url(self.shout_t, url)
            if i != 0:
                raise ShoutException(i, 'url is not correct')

    property genre:
        "A doc string can go here."

        def __get__(self):
            return shout_get_genre(self.shout_t)

        def __set__(self, genre):
            genre = str(genre)
            i = shout_set_genre(self.shout_t, genre)
            if i != 0:
                raise ShoutException(i, 'genre is not correct')

    property agent:
        "A doc string can go here."

        def __get__(self):
            return shout_get_agent(self.shout_t)

        def __set__(self, agent):
            agent = str(agent)
            i = shout_set_agent(self.shout_t, agent)
            if i != 0:
                raise ShoutException(i, 'Agent is not correct')

    property description:
        "A doc string can go here."

        def __get__(self):
            return shout_get_agent(self.shout_t)

        def __set__(self, description):
            description = str(description)
            i = shout_set_description(self.shout_t, description)
            if i != 0:
                raise ShoutException(i, 'Description is not correct')

    property dumpfile:
        "A doc string can go here."

        def __get__(self):
            return shout_get_dumpfile(self.shout_t)

        def __set__(self, dumpfile):
            dumpfile = str(dumpfile)
            i = shout_set_dumpfile(self.shout_t, dumpfile)
            if i != 0:
                raise ShoutException(i, 'Dumpfile is not correct')

    property audio_info:
        "A doc string can go here."

        def __get__(self):
            return self.__audio_info

        def __set__(self, dict):
            #get the current module
            pylibshout = globals()['pylibshout']

            for key, value in dict.items():
                const = 'SHOUT_AI_%s' % key.upper()
                if hasattr(pylibshout, const):
                    value = str(value)
                    i = shout_set_audio_info(self.shout_t, key, value)
                    self.__audio_info[key] = value
                else:
                    raise ShoutException('%s is not a valid audio_info attribute' % key)

            if i != 0:
                raise ShoutException(i, 'Audio info is not correct')

    property metadata:
        """Sets MP3 metadata. Only key is now 'song' :S 
        Returns:
            SHOUTERR_SUCCESS
            SHOUTERR_UNSUPPORTED if format isn't MP3
            SHOUTERR_MALLOC
            SHOUTERR_INSANE
            SHOUTERR_NOCONNECT"""

        def __get__(self):
            return self.__metadata

        def __set__(self, dict):
            for key, value in dict.items():
                value = str(value)
                shout_metadata_add(self.shout_metadata_t, key, value)
                self.__metadata[key] = value

            i = shout_set_metadata(self.shout_t, self.shout_metadata_t)

            i = 0
            if i != 0:
                raise ShoutException(i, 'Metadata is not correct')
   
    property public:
        "A doc string can go here."

        def __get__(self):
            return shout_get_public(self.shout_t)

        def __set__(self, public):
            public = bool(public)
            i = shout_set_dumpfile(self.shout_t, public)
            if i != 0:
                raise ShoutException(i, 'Public is not correct')

    property format:
        "A doc string can go here."

        def __get__(self):
            return shout_get_format(self.shout_t)

        def __set__(self, format):
            format = int(format)
            i = shout_set_format(self.shout_t, format)
            if i != 0:
                raise ShoutException(i, 'Format is not correct')

    property protocol:
        """takes a SHOUT_PROTOCOL_xxxxx argument"""

        def __get__(self):
            return shout_get_protocol(self.shout_t)

        def __set__(self, protocol):
            protocol = int(protocol)
            i = shout_set_protocol(self.shout_t, protocol)
            if i != 0:
                raise ShoutException(i, 'Protocol is not correct')

    property nonblocking:
        "A doc string can go here."

        def __get__(self):
            return shout_get_nonblocking(self.shout_t)

        def __set__(self, nonblocking):
            nonblocking = int(nonblocking)
            i = shout_set_nonblocking(self.shout_t, nonblocking)
            if i != 0:
                raise ShoutException(i, 'Nonblocking is not correct')
