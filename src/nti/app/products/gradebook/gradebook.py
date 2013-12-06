#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Grade book definition

$Id$
"""
from __future__ import unicode_literals, print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface
from zope.annotation import factory as an_factory
from zope.container import contained as zcontained
from zope.annotation import interfaces as an_interfaces
from zope.mimetype import interfaces as zmime_interfaces

from pyramid.traversal import lineage

from persistent import Persistent

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.assessment import interfaces as asm_interfaces

from nti.contenttypes.courses import interfaces as course_interfaces

from nti.dataserver import containers as nti_containers
from nti.dataserver.datastructures import CreatedModDateTrackingObject

from nti.mimetype.mimetype import MIME_BASE

from nti.ntiids import ntiids

from nti.utils.property import alias
from nti.utils._compat import Implicit
from nti.utils.property import CachedProperty
from nti.utils.schema import SchemaConfigured
from nti.utils.schema import createDirectFieldProperties

from . import interfaces as grades_interfaces

class _NTIIDMixin(zcontained.Contained):

	_ntiid_type = None
	_ntiid_include_self_name = False
	_ntiid_default_provider = 'NextThought'

	@property
	def _ntiid_provider(self):
		return self._ntiid_default_provider

	@property
	def _ntiid_specific_part(self):
		try:
			parts = []
			for location in lineage(self):
				if grades_interfaces.IGradeBook.providedBy(location):
					continue
				parts.append(ntiids.escape_provider(location.__name__))
				if ICourseInstance.providedBy(location):
					break
			parts.reverse()
			result = '.'.join(parts)
			return result
		except (AttributeError):  # Not ready yet
			return None

	@CachedProperty('_ntiid_provider', '_ntiid_specific_part')
	def NTIID(self):
		provider = self._ntiid_provider
		if provider:
			return ntiids.make_ntiid(date=ntiids.DATE,
									 provider=provider,
									 nttype=self._ntiid_type,
									 specific=self._ntiid_specific_part)

@component.adapter(course_interfaces.ICourseInstance)
@interface.implementer(grades_interfaces.IGradeBook,
					   an_interfaces.IAttributeAnnotatable,
					   zmime_interfaces.IContentTypeAware)
class GradeBook(Implicit,
				nti_containers.AcquireObjectsOnReadMixin,
				nti_containers.CheckingLastModifiedBTreeContainer,
				nti_containers._IdGenerationMixin,
				zcontained.Contained,
				_NTIIDMixin):

	mimeType = mime_type = MIME_BASE + u'.gradebook'
	_ntiid_type = grades_interfaces.NTIID_TYPE_GRADE_BOOK

	def get_entry_by_assignment(self, assignmentId):
		for part in self.values():
			entry = part.get_entry_by_assignment(assignmentId)
			if entry is not None:
				return entry
		return None
		
	def get_entry_by_ntiid(self, ntiid):
		result = None
		type_ = ntiids.get_type(ntiid)
		if type_ == grades_interfaces.NTIID_TYPE_GRADE_BOOK_ENTRY:
			specific = ntiids.get_specific(ntiid)
			part, entry = specific.split('.')[-2:]
			result = self.get(part, {}).get(entry)
		return result

	@property
	def TotalPartWeight(self):
		result = reduce(lambda x, y: x + y.weight, self.values(), 0.0)
		return result

_GradeBookFactory = an_factory(GradeBook, 'GradeBook')

@interface.implementer(grades_interfaces.IGradeBookPart,
					   an_interfaces.IAttributeAnnotatable,
					   zmime_interfaces.IContentTypeAware)
class GradeBookPart(Implicit,
					nti_containers.AcquireObjectsOnReadMixin,
					nti_containers.CheckingLastModifiedBTreeContainer,
					SchemaConfigured,
					_NTIIDMixin):

	mimeType = mime_type = MIME_BASE + u'.gradebookpart'

	_ntiid_include_self_name = True
	_ntiid_type = grades_interfaces.NTIID_TYPE_GRADE_BOOK_PART

	createDirectFieldProperties(grades_interfaces.IGradeBookPart)

	__parent__ = None
	__name__ = alias('Name')

	def get_entry_by_assignment(self, assignmentId):
		for entry in self.values():
			if entry.assignmentId == assignmentId:
				return entry
		return None
	
	@property
	def TotalEntryWeight(self):
		result = reduce(lambda x, y: x + y.weight, self.values(), 0.0)
		return result

	def __str__(self):
		return self.displayName

	def __repr__(self):
		return "%s(%s,%s)" % (self.__class__.__name__, self.displayName, self.weight)

@interface.implementer(grades_interfaces.IGradeBookEntry,
					   an_interfaces.IAttributeAnnotatable,
					   zmime_interfaces.IContentTypeAware)
class GradeBookEntry(Persistent,
					 CreatedModDateTrackingObject,
					 SchemaConfigured,
					 _NTIIDMixin,
					 Implicit):

	mimeType = mime_type = MIME_BASE + u'.gradebookentry'

	_ntiid_include_self_name = True
	_ntiid_type = grades_interfaces.NTIID_TYPE_GRADE_BOOK_ENTRY
	
	createDirectFieldProperties(grades_interfaces.IGradeBookEntry)

	__parent__ = None
	__name__ = alias('Name')

	ntiid = alias('NTIID')
	gradeScheme = alias('GradeScheme')

	@property
	def DueDate(self):
		asm = component.queryUtility(asm_interfaces.IQAssignment, name=self.assignmentId)
		return getattr(asm, 'available_for_submission_ending', None)

	def __str__(self):
		return self.displayName

	def __repr__(self):
		return "%s(%s,%s,%s)" % (self.__class__.__name__, self.displayName, self.weight,
								 self.assignmentId)

	def __eq__(self, other):
		try:
			return self is other or (self.NTIID == other.NTIID)
		except AttributeError:
			return NotImplemented

	def __hash__(self):
		xhash = 47
		xhash ^= hash(self.NTIID)
		return xhash
