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
from nti.dataserver.interfaces import ALL_PERMISSIONS
from nti.dataserver.datastructures import CreatedModDateTrackingObject
from nti.externalization.externalization import make_repr

from nti.utils.property import alias
from nti.utils.property import CachedProperty
from nti.utils.property import Lazy

from nti.utils.schema import SchemaConfigured
from nti.utils.schema import createDirectFieldProperties

from .interfaces import IGrade
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import ace_denying_all


@interface.implementer(IGrade,
					   zmime_interfaces.IContentTypeAware)
class Grade(CreatedModDateTrackingObject, # NOTE: This is *not* persistent
			SchemaConfigured,
			zcontained.Contained):

	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass

	createDirectFieldProperties(IGrade)

	grade = alias('value')
	username = alias('Username')
	assignmentId = alias('AssignmentId')
	Username = alias('__name__')

	# Right now, we inherit the 'creator' property
	# from CreatedModDateTrackingObject, but we have no real
	# need for it (also, some extent objects in the database
	# don't have a value for it), so provide a default that
	# ignores it
	creator = None

	def __init__(self, **kwargs):
		if 'grade' in kwargs and 'value' not in kwargs:
			kwargs['value'] = kwargs['grade']
			del kwargs['grade']
		if 'username' in kwargs and 'Username' not in kwargs:
			kwargs['Username'] = kwargs['username']
			del kwargs['username']
		super(Grade,self).__init__(**kwargs)

	@Lazy
	def createdTime(self):
		# Some old objects in the database won't have
		# a value for created time; in that case,
		# default to lastModified.
		# Some old objects in the database will have a lastModified
		# of 0, though, nothing we can do about that...
		return self.lastModified

	@property
	def AssignmentId(self):
		if self.__parent__ is not None:
			return self.__parent__.AssignmentId

	@CachedProperty
	def __acl__(self):
		acl = acl_from_aces()

		course = ICourseInstance(self, None)
		if course is not None:
			acl.extend((ace_allowing(i, ALL_PERMISSIONS) for i in course.instructors))
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

	__repr__ = make_repr()
