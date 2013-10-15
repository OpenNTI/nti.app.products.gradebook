#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Grade book

$Id$
"""
from __future__ import unicode_literals, print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope.container import contained as zcontained
from zope.annotation import interfaces as an_interfaces
from zope.mimetype import interfaces as zmime_interfaces

from persistent import Persistent

from nti.dataserver import mimetype
from nti.dataserver import containers as nti_containers
from nti.dataserver import interfaces as nti_interfaces
from nti.dataserver.datastructures import CreatedModDateTrackingObject

from nti.ntiids.ntiids import make_ntiid

from nti.utils.property import CachedProperty
from nti.utils.schema import SchemaConfigured
from nti.ntiids.ntiids import DATE as NTIID_DATE
from nti.utils.schema import createDirectFieldProperties

from . import interfaces as grades_interfaces

class _NTIIDMixin(zcontained.Contained):
	creator = None

	_ntiid_type = None
	_ntiid_include_parent_name = False

	@property
	def _ntiid_creator_username(self):
		return self.creator.username if self.creator else nti_interfaces.SYSTEM_USER_NAME

	@property
	def _ntiid_specific_part(self):
		if not self._ntiid_include_parent_name:
			return self.__name__
		try:
			if self.__parent__.__name__:
				return self.__parent__.__name__ + '.' + self.__name__
			else:
				return None
		except (AttributeError):  # Not ready yet
			return None

	@CachedProperty('_ntiid_creator_username', '_ntiid_specific_part')
	def NTIID(self):
		creator_name = self._ntiid_creator_username
		if creator_name:
			return make_ntiid(date=NTIID_DATE,
							  provider=creator_name,
							  nttype=self._ntiid_type,
							  specific=self._ntiid_specific_part)

@interface.implementer(grades_interfaces.IGradeBook,
					   an_interfaces.IAttributeAnnotatable,
					   zmime_interfaces.IContentTypeAware)
class GradeBook(nti_containers.CheckingLastModifiedBTreeContainer, _NTIIDMixin):
	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass
	_ntiid_type = grades_interfaces.NTIID_TYPE_GRADE_BOOK
	_ntiid_include_parent_name = True

@interface.implementer(grades_interfaces.IGradeBookPart,
					   an_interfaces.IAttributeAnnotatable,
					   zmime_interfaces.IContentTypeAware)
class GradeBookPart(nti_containers.CheckingLastModifiedBTreeContainer,
					_NTIIDMixin,
					SchemaConfigured):

	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass
	_ntiid_type = grades_interfaces.NTIID_TYPE_GRADE_BOOK_PART

	createDirectFieldProperties(grades_interfaces.IGradeBookPart)

	def __str__(self):
		return self.name

	def __repr__(self):
		return "%s(%s,%s)" % (self.__class__.__name__, self.name, self.weight)


@interface.implementer(grades_interfaces.IGradeBookEntry,
					   an_interfaces.IAttributeAnnotatable,
					   zmime_interfaces.IContentTypeAware)
class GradeBookEntry(Persistent,
					 CreatedModDateTrackingObject,
					 _NTIIDMixin,
					 SchemaConfigured):

	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass
	_ntiid_type = grades_interfaces.NTIID_TYPE_GRADE_BOOK_ENTRY

	createDirectFieldProperties(grades_interfaces.IGradeBookEntry)

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
