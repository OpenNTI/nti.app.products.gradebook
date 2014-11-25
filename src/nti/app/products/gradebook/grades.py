#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Grades definition

.. $Id$
"""
from __future__ import unicode_literals, print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from zope.container import contained as zcontained

from zope.mimetype.interfaces import IContentTypeAware

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.authorization_acl import ace_denying_all

from nti.dataserver.interfaces import ALL_PERMISSIONS
from nti.dataserver.datastructures import CreatedModDateTrackingObject

from nti.externalization.representation import WithRepr

from nti.mimetype import mimetype

from nti.schema.schema import EqHash
from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import createDirectFieldProperties

from nti.utils.property import Lazy
from nti.utils.property import alias

from nti.wref.interfaces import IWeakRef

from .interfaces import IGrade

@interface.implementer(	IGrade, IContentTypeAware)
@WithRepr
@EqHash('username', 'assignmentId', 'value')
class Grade(CreatedModDateTrackingObject, # NOTE: This is *not* persistent
			SchemaConfigured,
			zcontained.Contained):

	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass

	createDirectFieldProperties(IGrade)

	grade = alias('value')
	username = alias('Username')
	Username = alias('__name__')
	assignmentId = alias('AssignmentId')

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

	@property # Since we're not persistent, the regular use of CachedProperty fails
	def __acl__(self):
		acl = acl_from_aces()
		course = ICourseInstance(self, None)
		if course is not None:
			acl.extend((ace_allowing(i, ALL_PERMISSIONS) for i in course.instructors))
		if self.Username: # This will become conditional on whether we are published
			acl.append( ace_allowing(self.Username, ACT_READ) )
		acl.append( ace_denying_all() )
		return acl

@interface.implementer(IWeakRef)
@component.adapter(IGrade)
class GradeWeakRef(object):
	"""
	A weak reference to a grade. Because grades are non-persistent,
	we reference them by name inside of a part of a gradebook.
	This means that we can resolve to different object instances
	even during the same transaction, although they are logically the same
	grade.
	"""

	__slots__ = ('_part_wref', '_username')

	def __init__( self, grade ):
		if grade.__parent__ is None or not grade.Username:
			raise TypeError("Too soon, grade has no parent or username")

		self._part_wref = IWeakRef(grade.__parent__)
		self._username = grade.Username

	def __call__(self):
		part = self._part_wref()
		if part is not None:
			return part.get(self._username)

	def __eq__(self, other):
		try:
			return 	self is other or \
					(self._username, self._part_wref) == (other._username, other._part_wref)
		except AttributeError:
			return NotImplemented

	def __hash__(self):
		return hash((self._username, self._part_wref))

	def __getstate__(self):
		return self._part_wref, self._username

	def __setstate__(self, state):
		self._part_wref, self._username = state
