#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Relating to ACL implementations for objects defined in this package.

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from nti.contenttypes.courses.interfaces import ICourseInstance
from .interfaces import IGradeBook
from nti.dataserver.interfaces import IACLProvider

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import ace_denying_all


from nti.utils.property import Lazy

@interface.implementer(IACLProvider)
@component.adapter(IGradeBook)
class _GradeBookACLProvider(object):
	"""
	Only instructors can see the gradebook and its parts,
	but the parts cannot be changed (though individual grades
	within can be changed)
	"""

	def __init__(self, context):
		self.context = context

 	@Lazy
	def __acl__(self):
		acl = acl_from_aces()

		course = ICourseInstance(self.context, None)
		if course is not None:
			acl.extend( (ace_allowing(i, ACT_READ) for i in course.instructors) )

		acl.append( ace_denying_all() )

		return acl
