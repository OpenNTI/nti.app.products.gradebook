#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Grade book

$Id$
"""
from __future__ import unicode_literals, print_function, absolute_import
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope.container import contained as zcontained
from zope.annotation import interfaces as an_interfaces
from zope.mimetype import interfaces as zmime_interfaces

from persistent import Persistent

from nti.dataserver import mimetype
from nti.dataserver import containers as nti_containers
from nti.dataserver.datastructures import CreatedModDateTrackingObject

from nti.utils.schema import AdaptingFieldProperty

from . import interfaces as grades_interfaces

@interface.implementer(grades_interfaces.IGradeBook, an_interfaces.IAttributeAnnotatable, zmime_interfaces.IContentTypeAware)
class GradeBook(nti_containers.CheckingLastModifiedBTreeContainer, zcontained.Contained):

	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass

@interface.implementer(grades_interfaces.IGradeBookPart, an_interfaces.IAttributeAnnotatable, zmime_interfaces.IContentTypeAware)
class GradeBookPart(nti_containers.CheckingLastModifiedBTreeContainer, zcontained.Contained):

	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass

	name = AdaptingFieldProperty(grades_interfaces.IGradeBookEntry['name'])
	order = AdaptingFieldProperty(grades_interfaces.IGradeBookEntry['order'])
	weight = AdaptingFieldProperty(grades_interfaces.IGradeBookEntry['weight'])

	def __str__(self):
		return self.name

	def __repr__(self):
		return "%s(%s,%s)" % (self.__class__.__name__, self.name, self.weight)


@interface.implementer(grades_interfaces.IGradeBookEntry, an_interfaces.IAttributeAnnotatable, zmime_interfaces.IContentTypeAware)
class GradeBookEntry(Persistent, CreatedModDateTrackingObject, zcontained.Contained):

	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass

	name = AdaptingFieldProperty(grades_interfaces.IGradeBookEntry['name'])
	order = AdaptingFieldProperty(grades_interfaces.IGradeBookEntry['order'])
	NTIID = AdaptingFieldProperty(grades_interfaces.IGradeBookEntry['NTIID'])
	weight = AdaptingFieldProperty(grades_interfaces.IGradeBookEntry['weight'])
	questionSetID = AdaptingFieldProperty(grades_interfaces.IGradeBookEntry['questionSetID'])

	def __str__(self):
		return self.name

	def __repr__(self):
		return "%s(%s,%s,%s)" % (self.__class__.__name__, self.name, self.weight, self.NTIID)

	def __eq__(self, other):
		try:
			return self is other or (grades_interfaces.IGradeBookEntry.providedBy(other)
									 and self.NTIID == other.NTIID)
		except AttributeError:
			return NotImplemented

	def __hash__(self):
		xhash = 47
		xhash ^= hash(self.NTIID)
		return xhash
