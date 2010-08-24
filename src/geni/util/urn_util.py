#----------------------------------------------------------------------
# Copyright (c) 2010 Raytheon BBN Technologies
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and/or hardware specification (the "Work") to
# deal in the Work without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Work, and to permit persons to whom the Work
# is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Work.
#
# THE WORK IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE WORK OR THE USE OR OTHER DEALINGS
# IN THE WORK.
#----------------------------------------------------------------------
'''
URN creation and verification utilities.
'''

import re

# Translate publicids to URN format.
# The order of these rules matters
# because we want to catch things like double colons before we
# translate single colons. This is only a subset of the rules.
# See the GENI Wiki: GAPI_Identifiers
# See http://www.faqs.org/rfcs/rfc3151.html
publicid_xforms = [('%',  '%25'),
                   (';',  '%3B'),
                   ('+',  '%2B'),
                   (' ',  '+'  ), # note you must first collapse WS
                   ('#',  '%23'),
                   ('?',  '%3F'),
                   ("'",  '%27'),
                   ('::', ';'  ),
                   (':',  '%3A'),
                   ('//', ':'  ),
                   ('/',  '%2F')]

# FIXME: See sfa/util/namespace/URN_PREFIX which is ...:IDN
publicid_urn_prefix = 'urn:publicid:'

# validate urn
# Note that this is not sufficient but it is necessary
def is_valid_urn_string(instr):
    '''Could this string be part of a URN'''
    if instr is None or not isinstance(instr, str):
        return False
    #No whitespace
    # no # or ? or /
    if re.search("[\s|\?\/\#]", instr) is None:
        return True
    return False

# Note that this is not sufficient but it is necessary
def is_valid_urn(inurn):
    ''' Check that this string is a valid URN'''
    return is_valid_urn_string(inurn) and inurn.startswith(publicid_urn_prefix)

def urn_to_publicid(urn):
    '''Convert a URN like urn:publicid:... to a publicid'''
    # Remove prefix
    if urn is None or not is_valid_urn(urn):
        # Erroneous urn for conversion
        raise ValueError('Invalid urn: ' + urn)
    publicid = urn[len(publicid_urn_prefix):]
    # return the un-escaped string
    return urn_to_string_format(publicid)

def publicid_to_urn(id):
    '''Convert a publicid to a urn like urn:publicid:.....'''
    # prefix with 'urn:publicid:' and escape chars
    return publicid_urn_prefix + string_to_urn_format(id)

def string_to_urn_format(instr):
    '''Make a string URN compatible, collapsing whitespace and escaping chars'''
    if instr is None or instr.strip() == '':
        raise ValueError("Empty string cant be in a URN")
    # Collapse whitespace
    instr = ' '.join(instr.strip().split())
    for a, b in publicid_xforms:
        instr = instr.replace(a, b)
    return instr

def urn_to_string_format(urnstr):
    '''Turn a part of a URN into publicid format, undoing transforms'''
    if urnstr is None or urnstr.strip() == '':
        return urnstr
    # Validate it is reasonable URN string?
    for a, b in reversed(publicid_xforms):
        publicid = urnstr.replace(b, a)
    return publicid