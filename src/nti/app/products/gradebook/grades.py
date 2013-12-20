#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Grades definition

$Id$
"""
from __future__ import unicode_literals, print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.container import contained as zcontained

from zope.mimetype import interfaces as zmime_interfaces


from nti.dataserver import mimetype
from nti.dataserver.datastructures import ModDateTrackingObject
from nti.externalization.externalization import make_repr

from nti.dataserver.traversal import find_interface

from nti.utils.property import alias
from nti.utils.schema import SchemaConfigured
from nti.utils.schema import createDirectFieldProperties

from .interfaces import IGrade
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_UPDATE
from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import ace_denying_all

@interface.implementer(IGrade,
					   zmime_interfaces.IContentTypeAware)
class Grade(ModDateTrackingObject, # NOTE: This is *not* persistent
			SchemaConfigured,
			zcontained.Contained):

	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass

	createDirectFieldProperties(IGrade)

#	ntiid = alias('NTIID')

	grade = alias('value')
	username = alias('Username')
	assignmentId = alias('AssignmentId')
	Username = alias('__name__')

	def __init__(self, **kwargs):
		if 'grade' in kwargs and 'value' not in kwargs:
			kwargs['value'] = kwargs['grade']
			del kwargs['grade']
		if 'username' in kwargs and 'Username' not in kwargs:
			kwargs['Username'] = kwargs['username']
			del kwargs['username']
		super(Grade,self).__init__(**kwargs)

	@property
	def AssignmentId(self):
		if self.__parent__ is not None:
			return self.__parent__.AssignmentId

	def __conform__(self, iface):
		if ICourseInstance.isOrExtends(iface):
			try:
				return find_interface(self, ICourseInstance)
			except TypeError:
				logger.warn( "incorrect lineage for grade, should be tests only", exc_info=True)
				return None

	@property
	def __acl__(self):
		acl = acl_from_aces()

		course = ICourseInstance(self, None)
		if course is not None:
			acl.extend( (ace_allowing(i, ACT_UPDATE) for i in course.instructors) )
		if self.Username: # This will become conditional on whether we are published
			acl.append( ace_allowing(self.Username, ACT_READ) )
		acl.append( ace_denying_all() )

		return acl

	def __eq__(self, other):
		try:
			return self is other or (self.username == other.username
									 and self.assignmentId == other.assignmentId
									 and self.value == other.value )

		except AttributeError:
			return NotImplemented

#	def __hash__(self):
#		xhash = 47
#		xhash ^= hash(self.NTIID)
#		xhash ^= hash(self.username)
#		return xhash


	__repr__ = make_repr()
