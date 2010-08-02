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
The GPO Reference Aggregate Manager, showing how to implement
the GENI AM API. This AggregateManager has only fake resources.
"""

import base64
import datetime
import logging
import xml.dom.minidom as minidom
import xmlrpclib
import zlib

import dateutil.parser

import geni

# See sfa/trust/rights.py
# These are names of operations
# from the rights.py privilege_table
# Credentials may list privileges that
# map to these operations, giving the caller permission
# to perform the functions
RENEWSLIVERPRIV = 'renewsliver'
CREATESLIVERPRIV = 'createsliver'
DELETESLIVERPRIV = 'deleteslice'
SLIVERSTATUSPRIV = 'getsliceresources'
SHUTDOWNSLIVERPRIV = 'shutdown'

RESOURCEPUBLICIDPREFIX = 'geni.net'
REFAM_MAXLEASE_DAYS = 365


class Resource(object):
    """A Resource has an id, a type, and a boolean indicating availability."""

    def __init__(self, id, type):
        self._id = id
        self._type = type
        self.available = True

    def toxml(self):
        template = ('<resource><type>%s</type><id>%s</id>'
                    + '<available>%r</available></resource>')
        return template % (self._type, self._id, self.available)

    def urn(self):
        publicid = 'IDN %s//resource//%s_%s' % (RESOURCEPUBLICIDPREFIX, self._type, str(self._id))
        return geni.publicid_to_urn(publicid)

    def __eq__(self, other):
        return self._id == other._id

    def __neq__(self, other):
        return self._id != other._id

    @classmethod
    def fromdom(cls, element):
        """Create a Resource instance from a DOM representation."""
        type = element.getElementsByTagName('type')[0].firstChild.data
        id = int(element.getElementsByTagName('id')[0].firstChild.data)
        return Resource(id, type)

class Sliver(object):
    """A sliver has a URN, a list of resources, and an expiration time."""

    def __init__(self, urn, expiration=datetime.datetime.now()):
        self.urn = urn
        self.resources = list()
        self.expiration = expiration


class ReferenceAggregateManager(object):
    '''A reference Aggregate Manager that manages fake resources.'''
    
    # root_cert is a single cert or dir of multiple certs
    # that are trusted to sign credentials
    def __init__(self, root_cert):
        self._slivers = dict()
        self._resources = [Resource(x, 'Nothing') for x in range(10)]
        self._cred_verifier = geni.CredentialVerifier(root_cert)
        self.max_lease = datetime.timedelta(days=REFAM_MAXLEASE_DAYS)
        self.logger = logging.getLogger('gam.reference')

    def GetVersion(self):
        '''Specify version information about this AM. That could 
        include API version information, RSpec format and version
        information, etc. Return a dict.'''
        self.logger.info("Called GetVersion")
        return dict(geni_api=1)

    def ListResources(self, credentials, options):
        '''Return an RSpec of resources managed at this AM. 
        If a geni_slice_urn
        is given in the options, then only return resources assigned 
        to that slice. If geni_available is specified in the options,
        then only report available resources. And if geni_compressed
        option is specified, then compress the result.'''
        self.logger.info('ListResources(%r)' % (options))
        # Note this list of privileges is really the name of an operation
        # from the privilege_table in sfa/trust/rights.py
        # Credentials will specify a list of privileges, each of which
        # confers the right to perform a list of operations.
        # EG the 'info' privilege in a credential allows the operations
        # listslices, listnodes, policy

        # could require list or listnodes?
        privileges = ()
        # Note that verify throws an exception on failure.
        # Use the client PEM format cert as retrieved
        # from the https connection by the SecureXMLRPCServer
        # to identify the caller.
        self._cred_verifier.verify_from_strings(self._server.pem_cert,
                                                credentials,
                                                None,
                                                privileges)
        # If we get here, the credentials give the caller
        # all needed privileges to act on the given target.

        if not options:
            options = dict()

        if 'geni_slice_urn' in options:
            slice_urn = options['geni_slice_urn']
            if slice_urn in self._slivers:
                sliver = self._slivers[slice_urn]
                result = ('<rspec>'
                          + ''.join([x.toxml() for x in sliver.resources])
                          + '</rspec>')
            else:
                # return an empty rspec
                result = '<rspec/>'
        elif 'geni_available' in options and options['geni_available']:
            result = ('<rspec>' + ''.join([x.toxml() for x in self._resources])
                      + '</rspec>')
        else:
            all_resources = list()
            all_resources.extend(self._resources)
            for sliver in self._slivers:
                all_resources.extend(self._slivers[sliver].resources)
            result = ('<rspec>' + ''.join([x.toxml() for x in all_resources])
                      + '</rspec>')

#        self.logger.debug('Returning resource list %s', result)

        # Optionally compress the result
        if 'geni_compressed' in options and options['geni_compressed']:
            result = base64.b64encode(zlib.compress(result))
        return result

    def CreateSliver(self, slice_urn, credentials, rspec, users):
        """Create a sliver with the given URN from the resources in 
        the given RSpec.
        Return an RSpec of the actually allocated resources.
        users argument provides extra information on configuring the resources
        for runtime access.
        """
        self.logger.info('CreateSliver(%r)' % (slice_urn))
        # Note this list of privileges is really the name of an operation
        # from the privilege_table in sfa/trust/rights.py
        # Credentials will specify a list of privileges, each of which
        # confers the right to perform a list of operations.
        # EG the 'info' privilege in a credential allows the operations
        # listslices, listnodes, policy
        privileges = (CREATESLIVERPRIV,)
        # Note that verify throws an exception on failure.
        # Use the client PEM format cert as retrieved
        # from the https connection by the SecureXMLRPCServer
        # to identify the caller.
        creds = self._cred_verifier.verify_from_strings(self._server.pem_cert,
                                                        credentials,
                                                        slice_urn,
                                                        privileges)
        # If we get here, the credentials give the caller
        # all needed privileges to act on the given target.
        if slice_urn in self._slivers:
            self.logger.error('Sliver %s already exists.' % slice_urn)
            raise Exception('Sliver %s already exists.' % slice_urn)

        rspec_dom = None
        try:
            rspec_dom = minidom.parseString(rspec)
        except Exception, exc:
            self.logger.error("Cant create sliver %s. Exception parsing rspec: %s" % (slice_urn, exc))
            raise Exception("Cant create sliver %s. Exception parsing rspec: %s" % (slice_urn, exc))

        resources = list()
        for elem in rspec_dom.documentElement.childNodes:
            resource = Resource.fromdom(elem)
            if resource not in self._resources:
                self.logger.info("Requested resource %d not available" % resource._id)
                raise Exception('Resource %d not available' % resource._id)
            resources.append(resource)

        # determine max expiration time from credentials
        expiration = datetime.datetime.now() + self.max_lease
        for cred in creds:
            if cred.expiration < expiration:
                expiration = cred.expiration

        sliver = Sliver(slice_urn, expiration)

        # remove resources from available list
        for resource in resources:
            sliver.resources.append(resource)
            self._resources.remove(resource)
            resource.available = False

        self._slivers[slice_urn] = sliver

        self.logger.info("Created new sliver for slice %s" % slice_urn)
        return ('<rspec>' + ''.join([x.toxml() for x in sliver.resources])
                + '</rspec>')

    def DeleteSliver(self, slice_urn, credentials):
        '''Stop and completely delete the named sliver, and return True.'''
        self.logger.info('DeleteSliver(%r)' % (slice_urn))
        # Note this list of privileges is really the name of an operation
        # from the privilege_table in sfa/trust/rights.py
        # Credentials will specify a list of privileges, each of which
        # confers the right to perform a list of operations.
        # EG the 'info' privilege in a credential allows the operations
        # listslices, listnodes, policy
        privileges = (DELETESLIVERPRIV,)
        # Note that verify throws an exception on failure.
        # Use the client PEM format cert as retrieved
        # from the https connection by the SecureXMLRPCServer
        # to identify the caller.
        self._cred_verifier.verify_from_strings(self._server.pem_cert,
                                                credentials,
                                                slice_urn,
                                                privileges)
        # If we get here, the credentials give the caller
        # all needed privileges to act on the given target.
        if slice_urn in self._slivers:
            sliver = self._slivers[slice_urn]
            # return the resources to the pool
            self._resources.extend(sliver.resources)
            for resource in sliver.resources:
                resource.available = True
            del self._slivers[slice_urn]
            self.logger.info("Sliver %r deleted" % slice_urn)
            return True
        else:
            self.no_such_slice(slice_urn)

    def SliverStatus(self, slice_urn, credentials):
        '''Report as much as is known about the status of the resources
        in the sliver. The AM may not know.
        Return a dict of sliver urn, status, and a list of dicts resource
        statuses.'''
        # Loop over the resources in a sliver gathering status.
        self.logger.info('SliverStatus(%r)' % (slice_urn))
        # Note this list of privileges is really the name of an operation
        # from the privilege_table in sfa/trust/rights.py
        # Credentials will specify a list of privileges, each of which
        # confers the right to perform a list of operations.
        # EG the 'info' privilege in a credential allows the operations
        # listslices, listnodes, policy
        privileges = (SLIVERSTATUSPRIV,)
        self._cred_verifier.verify_from_strings(self._server.pem_cert,
                                                credentials,
                                                slice_urn,
                                                privileges)
        if slice_urn in self._slivers:
            sliver = self._slivers[slice_urn]
            # Now calculate the status of the sliver
            res_status = list()
            for res in sliver.resources:
                # Gather the status of all the resources
                # in the sliver. This could be actually
                # communicating with the resources, or simply
                # reporting the state of initialized, started, stopped, ...
                res_status.append(dict(geni_urn=res.urn(),
                                       geni_status='ready',
                                       geni_error=''))
            self.logger.info("Calculated and returning sliver %r status" % slice_urn)
            return dict(geni_urn=sliver.urn,
                        # TODO: need to calculate sliver status
                        # as some kind of sum of the resource status
                        geni_status='ready',
                        geni_resources=res_status)
        else:
            self.no_such_slice(slice_urn)

    def RenewSliver(self, slice_urn, credentials, expiration_time):
        '''Renew the local sliver that is part of the named Slice
        until the given expiration time.
        Return False on any error, True on success.'''

        self.logger.info('RenewSliver(%r, %r)' % (slice_urn, expiration_time))
        privileges = (RENEWSLIVERPRIV,)
        creds = self._cred_verifier.verify_from_strings(self._server.pem_cert,
                                                        credentials,
                                                        slice_urn,
                                                        privileges)
        if slice_urn in self._slivers:
            sliver = self._slivers.get(slice_urn)
            requested = dateutil.parser.parse(str(expiration_time))
            for cred in creds:
                # FIXME Should this fail if 1 cred will have expired? Or only if all will be expired?
                # Or in practics is this always a list of 1?
                if cred.expiration < requested:
                    self.logger.debug("Cant renew sliver %r until %r cause one of %d credential(s) (%r) expires before then", slice_urn, expiration_time, len(creds), cred.get_gid_object().get_hrn())
                    return False

            sliver.expiration = requested
            self.logger.info("Sliver %r now expires on %r", slice_urn, expiration_time)
            return True
        else:
            self.no_such_slice(slice_urn)

    def Shutdown(self, slice_urn, credentials):
        '''For Management Authority / operator use: shut down a badly
        behaving sliver, without deleting it to allow for forensics.'''
        self.logger.info('Shutdown(%r)' % (slice_urn))
        privileges = (SHUTDOWNSLIVERPRIV,)
        self._cred_verifier.verify_from_strings(self._server.pem_cert,
                                                        credentials,
                                                        slice_urn,
                                                        privileges)
        if slice_urn in self._slivers:
            # FIXME: Could change the status to stopped
            # and actually honor that elsewhere
            # FIXME: Should return True on success
            return False
        else:
            self.no_such_slice(slice_urn)

    def no_such_slice(self, slice_urn):
        """Raise a no such slice exception."""
        fault_code = 'No such slice.'
        fault_string = 'The slice named by %s does not exist' % (slice_urn)
        raise xmlrpclib.Fault(fault_code, fault_string)
