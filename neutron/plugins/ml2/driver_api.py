# Copyright (c) 2013 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from abc import ABCMeta, abstractmethod, abstractproperty

# The following keys are used in the segment dictionaries passed via
# the driver API. These are defined separately from similar keys in
# neutron.extensions.providernet so that drivers don't need to change
# if/when providernet moves to the core API.
#
NETWORK_TYPE = 'network_type'
PHYSICAL_NETWORK = 'physical_network'
SEGMENTATION_ID = 'segmentation_id'


class TypeDriver(object):
    """Define stable abstract interface for ML2 type drivers.

    ML2 type drivers each support a specific network_type for provider
    and/or tenant network segments. Type drivers must implement this
    abstract interface, which defines the API by which the plugin uses
    the driver to manage the persistent type-specific resource
    allocation state associated with network segments of that type.

    Network segments are represented by segment dictionaries using the
    NETWORK_TYPE, PHYSICAL_NETWORK, and SEGMENTATION_ID keys defined
    above, corresponding to the provider attributes.  Future revisions
    of the TypeDriver API may add additional segment dictionary
    keys. Attributes not applicable for a particular network_type may
    either be excluded or stored as None.
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def get_type(self):
        """Get driver's network type.

        :returns network_type value handled by this driver
        """
        pass

    @abstractmethod
    def initialize(self):
        """Perform driver initialization.

        Called after all drivers have been loaded and the database has
        been initialized. No abstract methods defined below will be
        called prior to this method being called.
        """
        pass

    @abstractmethod
    def validate_provider_segment(self, segment):
        """Validate attributes of a provider network segment.

        :param segment: segment dictionary using keys defined above
        :raises: neutron.common.exceptions.InvalidInput if invalid

        Called outside transaction context to validate the provider
        attributes for a provider network segment. Raise InvalidInput
        if:

         - any required attribute is missing
         - any prohibited or unrecognized attribute is present
         - any attribute value is not valid

        The network_type attribute is present in segment, but
        need not be validated.
        """
        pass

    @abstractmethod
    def reserve_provider_segment(self, session, segment):
        """Reserve resource associated with a provider network segment.

        :param session: database session
        :param segment: segment dictionary using keys defined above

        Called inside transaction context on session to reserve the
        type-specific resource for a provider network segment. The
        segment dictionary passed in was returned by a previous
        validate_provider_segment() call.
        """
        pass

    @abstractmethod
    def allocate_tenant_segment(self, session):
        """Allocate resource for a new tenant network segment.

        :param session: database session
        :returns: segment dictionary using keys defined above

        Called inside transaction context on session to allocate a new
        tenant network, typically from a type-specific resource
        pool. If successful, return a segment dictionary describing
        the segment. If tenant network segment cannot be allocated
        (i.e. tenant networks not supported or resource pool is
        exhausted), return None.
        """
        pass

    @abstractmethod
    def release_segment(self, session, segment):
        """Release network segment.

        :param session: database session
        :param segment: segment dictionary using keys defined above

        Called inside transaction context on session to release a
        tenant or provider network's type-specific resource. Runtime
        errors are not expected, but raising an exception will result
        in rollback of the transaction.
        """
        pass


class NetworkContext(object):
    """Context passed to MechanismDrivers for changes to network resources.

    A NetworkContext instance wraps a network resource. It provides
    helper methods for accessing other relevant information. Results
    from expensive operations are cached so that other
    MechanismDrivers can freely access the same information.
    """

    __metaclass__ = ABCMeta

    @abstractproperty
    def current(self):
        """Return the current state of the network.

        Return the current state of the network, as defined by
        NeutronPluginBaseV2.create_network and all extensions in the
        ml2 plugin.
        """
        pass

    @abstractproperty
    def original(self):
        """Return the original state of the network.

        Return the original state of the network, prior to a call to
        update_network. Method is only valid within calls to
        update_network_precommit and update_network_postcommit.
        """
        pass

    @abstractproperty
    def network_segments(self):
        """Return the segments associated with this network resource."""
        pass


class PortContext(object):
    """Context passed to MechanismDrivers for changes to port resources.

    A PortContext instance wraps a port resource. It provides helper
    methods for accessing other relevant information. Results from
    expensive operations are cached so that other MechanismDrivers can
    freely access the same information.
    """

    __metaclass__ = ABCMeta

    @abstractproperty
    def current(self):
        """Return the current state of the port.

        Return the current state of the port, as defined by
        NeutronPluginBaseV2.create_port and all extensions in the ml2
        plugin.
        """
        pass

    @abstractproperty
    def original(self):
        """Return the original state of the port

        Return the original state of the port, prior to a call to
        update_port. Method is only valid within calls to
        update_port_precommit and update_port_postcommit.
        """
        pass

    @abstractproperty
    def network(self):
        """Return the NetworkContext associated with this port."""
        pass


class MechanismDriver(object):
    """Define stable abstract interface for ML2 mechanism drivers.

    A mechanism driver is called on the creation, update, and deletion
    of networks and ports. For every event, there are two methods that
    get called - one within the database transaction (method suffix of
    _precommit), one right afterwards (method suffix of _postcommit).

    Exceptions raised by methods called inside the transaction can
    rollback, but should not make any blocking calls (for example,
    REST requests to an outside controller). Methods called after
    transaction commits can make blocking external calls, though these
    will block the entire process. Exceptions raised in calls after
    the transaction commits may cause the associated resource to be
    deleted.

    Because rollback outside of the transaction is not done in the
    update network/port case, all data validation must be done within
    methods that are part of the database transaction.
    """

    # TODO(apech): add calls for subnets

    __metaclass__ = ABCMeta

    @abstractmethod
    def initialize(self):
        """Perform driver initialization.

        Called after all drivers have been loaded and the database has
        been initialized. No abstract methods defined below will be
        called prior to this method being called.
        """
        pass

    def create_network_precommit(self, context):
        """Allocate resources for a new network.

        :param context: NetworkContext instance describing the new
        network.

        Create a new network, allocating resources as necessary in the
        database. Called inside transaction context on session. Call
        cannot block.  Raising an exception will result in a rollback
        of the current transaction.
        """
        pass

    def create_network_postcommit(self, context):
        """Create a network.

        :param context: NetworkContext instance describing the new
        network.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Raising an exception will
        cause the deletion of the resource.
        """
        pass

    def update_network_precommit(self, context):
        """Update resources of a network.

        :param context: NetworkContext instance describing the new
        state of the network, as well as the original state prior
        to the update_network call.

        Update values of a network, updating the associated resources
        in the database. Called inside transaction context on session.
        Raising an exception will result in rollback of the
        transaction.

        update_network_precommit is called for all changes to the
        network state. It is up to the mechanism driver to ignore
        state or state changes that it does not know or care about.
        """
        pass

    def update_network_postcommit(self, context):
        """Update a network.

        :param context: NetworkContext instance describing the new
        state of the network, as well as the original state prior
        to the update_network call.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Raising an exception will
        cause the deletion of the resource.

        update_network_postcommit is called for all changes to the
        network state.  It is up to the mechanism driver to ignore
        state or state changes that it does not know or care about.
        """
        pass

    def delete_network_precommit(self, context):
        """Delete resources for a network.

        :param context: NetworkContext instance describing the current
        state of the network, prior to the call to delete it.

        Delete network resources previously allocated by this
        mechanism driver for a network. Called inside transaction
        context on session. Runtime errors are not expected, but
        raising an exception will result in rollback of the
        transaction.
        """
        pass

    def delete_network_postcommit(self, context):
        """Delete a network.

        :param context: NetworkContext instance describing the current
        state of the network, prior to the call to delete it.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Runtime errors are not
        expected, and will not prevent the resource from being
        deleted.
        """
        pass

    def create_port_precommit(self, context):
        """Allocate resources for a new port.

        :param context: PortContext instance describing the port.

        Create a new port, allocating resources as necessary in the
        database. Called inside transaction context on session. Call
        cannot block.  Raising an exception will result in a rollback
        of the current transaction.
        """
        pass

    def create_port_postcommit(self, context):
        """Create a port.

        :param context: PortContext instance describing the port.

        Called after the transaction completes. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance.  Raising an exception will
        result in the deletion of the resource.
        """
        pass

    def update_port_precommit(self, context):
        """Update resources of a port.

        :param context: PortContext instance describing the new
        state of the port, as well as the original state prior
        to the update_port call.

        Called inside transaction context on session to complete a
        port update as defined by this mechanism driver. Raising an
        exception will result in rollback of the transaction.

        update_port_precommit is called for all changes to the port
        state. It is up to the mechanism driver to ignore state or
        state changes that it does not know or care about.
        """
        pass

    def update_port_postcommit(self, context):
        """Update a port.

        :param context: PortContext instance describing the new
        state of the port, as well as the original state prior
        to the update_port call.

        Called after the transaction completes. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance.  Raising an exception will
        result in the deletion of the resource.

        update_port_postcommit is called for all changes to the port
        state. It is up to the mechanism driver to ignore state or
        state changes that it does not know or care about.
        """
        pass

    def delete_port_precommit(self, context):
        """Delete resources of a port.

        :param context: PortContext instance describing the current
        state of the port, prior to the call to delete it.

        Called inside transaction context on session. Runtime errors
        are not expected, but raising an exception will result in
        rollback of the transaction.
        """
        pass

    def delete_port_postcommit(self, context):
        """Delete a port.

        :param context: PortContext instance describing the current
        state of the port, prior to the call to delete it.

        Called after the transaction completes. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance.  Runtime errors are not
        expected, and will not prevent the resource from being
        deleted.
        """
        pass
