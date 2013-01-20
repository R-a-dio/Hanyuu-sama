from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import re
import string

#: The character used for low level CTCP quoting.
_LOW_LEVEL_QUOTE = "\020"
#: Some kind of quoting char? No idea what this is for.
_CTCP_LEVEL_QUOTE = "\134"
#: Signifies the start and end of a CTCP message.
_CTCP_DELIMITER = "\001"

#: Regex used for separating lines in the IRC protocol.
#: Some IRC servers seem to use \n only as the delimiter.
_linesep_regexp = re.compile("\r?\n")

#: Regex used to split lines into their components, according to the IRC
#: specification. The regex groups are prefix, command and argument.
_rfc_1459_command_regexp = re.compile("^(:(?P<prefix>[^ ]+) +)?(?P<command>[^ ]+)( *(?P<argument> .+))?", re.UNICODE)

#: Character mapping for special characters in low level CTCP quoting.
_low_level_mapping = {
    "0": "\000",
    "n": "\n",
    "r": "\r",
    _LOW_LEVEL_QUOTE: _LOW_LEVEL_QUOTE
}

#: Regex used for dequoting CTCP quotes. I think.
_low_level_regexp = re.compile(_LOW_LEVEL_QUOTE + "(.)", re.UNICODE)


_special = "-[]\\`^{}"

#: The characters that are permitted in IRC nicknames
nick_characters = string.ascii_letters + string.digits + _special

#: A translation map for translating IRC lowercase and uppercase.
_ircstring_translation = string.maketrans(string.ascii_uppercase + "[]\\^",
                                        string.ascii_lowercase + "{}|~")

def mask_matches(nick, mask):
    """Check if a nick matches a mask.

    Returns True if the nick matches, otherwise False.
    """
    nick = irc_lower(nick)
    mask = irc_lower(mask)
    mask = mask.replace("\\", "\\\\")
    for ch in ".$|[](){}+":
        mask = mask.replace(ch, "\\" + ch)
    mask = mask.replace("?", ".")
    mask = mask.replace("*", ".*")
    r = re.compile(mask, re.IGNORECASE)
    return r.match(nick)



def irc_lower(s):
    """Returns a lowercased string.

    The definition of lowercased comes from the IRC specification (RFC
    1459).
    """
    if (type(s) == unicode):
        s = s.encode('utf-8')
    return s.translate(_ircstring_translation)

def _ctcp_dequote(message):
    """[Internal] Dequote a message according to CTCP specifications.

    The function returns a list where each element can be either a
    string (normal message) or a tuple of one or two strings (tagged
    messages).  If a tuple has only one element (ie is a singleton),
    that element is the tag; otherwise the tuple has two elements: the
    tag and the data.

        :params message: The message to be decoded.
    """

    def _low_level_replace(match_obj):
        ch = match_obj.group(1)

        # If low_level_mapping doesn't have the character as key, we
        # should just return the character.
        return _low_level_mapping.get(ch, ch)

    if _LOW_LEVEL_QUOTE in message:
        # Yup, there was a quote.  Release the dequoter, man!
        message = _low_level_regexp.sub(_low_level_replace, message)

    if _CTCP_DELIMITER not in message:
        return [message]
    else:
        # Split it into parts.  (Does any IRC client actually *use*
        # CTCP stacking like this?)
        chunks = message.split(_CTCP_DELIMITER)

        messages = []
        i = 0
        while i < len(chunks)-1:
            # Add message if it's non-empty.
            if len(chunks[i]) > 0:
                messages.append(chunks[i])

            if i < len(chunks)-2:
                # Aye!  CTCP tagged data ahead!
                messages.append(tuple(chunks[i+1].split(" ", 1)))

            i = i + 2

        if len(chunks) % 2 == 0:
            # Hey, a lonely _CTCP_DELIMITER at the end!  This means
            # that the last chunk, including the delimiter, is a
            # normal message!  (This is according to the CTCP
            # specification.)
            messages.append(_CTCP_DELIMITER + chunks[-1])

        return messages

def ip_numstr_to_quad(num):
    """Convert an IP number as an integer given in ASCII
    representation (e.g. '3232235521') to an IP address string
    (e.g. '192.168.0.1')."""
    n = long(num)
    p = map(str, map(int, [n >> 24 & 0xFF, n >> 16 & 0xFF,
                           n >> 8 & 0xFF, n & 0xFF]))
    return ".".join(p)

def ip_quad_to_numstr(quad):
    """Convert an IP address string (e.g. '192.168.0.1') to an IP
    number as an integer given in ASCII representation
    (e.g. '3232235521')."""
    p = map(long, quad.split("."))
    s = str((p[0] << 24) | (p[1] << 16) | (p[2] << 8) | p[3])
    if s[-1] == "L":
        s = s[:-1]
    return s

def nm_to_n(s):
    """Get the nick part of a nickmask.

    (The source of an :class:`connection.Event` is a nickmask.)
    """
    return s.split("!")[0]

def nm_to_uh(s):
    """Get the userhost part of a nickmask.

    (The source of an :class:`connection.Event` is a nickmask.)
    """
    return s.split("!")[1]

def nm_to_h(s):
    """Get the host part of a nickmask.

    (The source of an :class:`connection.Event` is a nickmask.)
    """
    return s.split("@")[1]

def nm_to_u(s):
    """Get the user part of a nickmask.

    (The source of an :class:`connection.Event` is a nickmask.)
    """
    s = s.split("!")[1]
    return s.split("@")[0]
