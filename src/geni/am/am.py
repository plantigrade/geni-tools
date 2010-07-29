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
"""
The Aggregate Manager server for the GENI Aggregate Manager.
Invoked from gam.py
Typically used with the ReferenceAggregateManager.
The GENI AM API is defined in the AggregateManager class.
"""

import os
import xmlrpclib
import zlib
from ..SecureXMLRPCServer import SecureXMLRPCServer

class AggregateManager(object):
    """The public API for a GENI Aggregate Manager.  This class provides the
    XMLRPC interface and invokes a delegate for all the operations.
    """

    def __init__(self, delegate):
        self._delegate = delegate
        
    def GetVersion(self):
        '''Specify version information about this AM. That could 
        include API version information, RSpec format and version
        information, etc. Return a dict.'''
        return self._delegate.GetVersion()

    def ListResources(self, credentials, options):
        '''Return an RSpec of resources managed at this AM. 
        If a geni_slice_urn
        is given in the options, then only return resources assigned 
        to that slice. If geni_available is specified in the options,
        then only report available resources. And if geni_compressed
        option is specified, then compress the result.'''
        return self._delegate.ListResources(credentials, options)

    def CreateSliver(self, slice_urn, credentials, rspec, users):
        """Create a sliver with the given URN from the resources in 
        the given RSpec.
        Return an RSpec of the actually allocated resources.
        users argument provides extra information on configuring the resources
        for runtime access.
        """
        return self._delegate.CreateSliver(slice_urn, credentials, rspec, users)

    def DeleteSliver(self, slice_urn, credentials):
        """Delete the given sliver. Return true on success."""
        return self._delegate.DeleteSliver(slice_urn, credentials)

    def SliverStatus(self, slice_urn, credentials):
        '''Report as much as is known about the status of the resources
        in the sliver. The AM may not know.'''
        return self._delegate.SliverStatus(slice_urn, credentials)

    def RenewSliver(self, slice_urn, credentials, expiration_time):
        """Extend the life of the given sliver until the given
        expiration time. Return False on error."""
        return self._delegate.RenewSliver(slice_urn, credentials,
                                          expiration_time)

    def Shutdown(self, slice_urn, credentials):
        '''For Management Authority / operator use: shut down a badly
        behaving sliver, without deleting it to allow for forensics.'''
        return self._delegate.Shutdown(slice_urn, credentials)

class PrintingAggregateManager(object):
    """A dummy AM that prints the called methods."""

    def GetVersion(self):
        print 'GetVersion()'
        return 1

    def ListResources(self, credentials, options):
        compressed = False
        if options and 'geni_compressed' in options:
            compressed  = options['geni_compressed']
        print 'ListResources(compressed=%r)' % (compressed)
        # return an empty rspec
        result = '<rspec/>'
        if compressed:
            result = xmlrpclib.Binary(zlib.compress(result))
        return result

    def CreateSliver(self, slice_urn, credentials, rspec, users):
        print 'CreateSliver(%r)' % (slice_urn)
        return '<rspec/>'

    def DeleteSliver(self, slice_urn, credentials):
        print 'DeleteSliver(%r)' % (slice_urn)
        return False

    def SliverStatus(self, slice_urn, credentials):
        print 'SliverStatus(%r)' % (slice_urn)
        raise Exception('No such slice.')

    def RenewSliver(self, slice_urn, credentials, expiration_time):
        print 'SliverStatus(%r, %r)' % (slice_urn, expiration_time)
        return False

    def Shutdown(self, slice_urn, credentials):
        print 'Shutdown(%r)' % (slice_urn)
        return False


class AggregateManagerServer(object):
    """An XMLRPC Aggregate Manager Server. Delegates calls to given delegate,
    or the default printing AM."""

    def __init__(self, addr, delegate=None, keyfile=None, certfile=None,
                 ca_certs=None):
        # ca_certs arg here must be a file of concatenated certs
        if ca_certs is None:
            raise Exception('Missing CA Certs')
        elif not os.path.isfile(os.path.expanduser(ca_certs)):
            raise Exception('CA Certs must be an existing file of accepted root certs: %s' % ca_certs)

        self._server = SecureXMLRPCServer(addr, keyfile=keyfile,
                                          certfile=certfile, ca_certs=ca_certs)
        if delegate is None:
            delegate = PrintingAggregateManager()
        self._server.register_instance(AggregateManager(delegate))
        # Set the server on the delegate so it can access the
        # client certificate.
        delegate._server = self._server

    def serve_forever(self):
        self._server.serve_forever()

    def register_instance(self, instance):
        # Pass the AM instance to the generic XMLRPC server,
        # which lets it know what XMLRPC methods to expose
        self._server.register_instance(instance)
