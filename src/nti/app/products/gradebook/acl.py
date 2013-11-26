#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Relating to ACL implementations for objects defined in this package.

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.dataserver import interfaces as nti_interfaces
from nti.dataserver.authorization_acl import AbstractCreatedAndSharedACLProvider

ALL_PERMISSIONS = nti_interfaces.ALL_PERMISSIONS

class _GradeBookACLProvider(AbstractCreatedAndSharedACLProvider):
	"""
	Grant full control to their creator and inherit moderation
	rights through their parent.
	"""

	_DENY_ALL = False

	def _get_sharing_target_names( self ):
		return ()

	def _extend_acl_after_creator_and_sharing(self, acl):
		self._extend_with_admin_privs(acl)
