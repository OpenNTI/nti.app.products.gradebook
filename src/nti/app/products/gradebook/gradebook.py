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
from nti.dataserver.traversal import find_interface

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.assessment.interfaces import IQAssignment

from nti.dataserver import containers as nti_containers
from nti.dataserver.users import User

from nti.mimetype.mimetype import MIME_BASE

from nti.ntiids import ntiids

from nti.utils.property import alias
from nti.utils.property import CachedProperty
from nti.utils.schema import SchemaConfigured
from nti.utils.schema import createDirectFieldProperties

from nti.externalization.externalization import make_repr

from .interfaces import IGradeBook
from .interfaces import IGradeBookPart
from .interfaces import IGradeBookEntry
from .interfaces import ISubmittedAssignmentHistory
from .interfaces import NTIID_TYPE_GRADE_BOOK
from .interfaces import NTIID_TYPE_GRADE_BOOK_PART
from .interfaces import NTIID_TYPE_GRADE_BOOK_ENTRY
from .interfaces import NO_SUBMIT_PART_NAME

class _NTIIDMixin(object):

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
				if IGradeBook.providedBy(location):
					continue
				parts.append(ntiids.escape_provider(location.__name__))
				if ICourseInstance.providedBy(location):
					break
			parts.reverse()
			result = None
			if None not in parts:
				result = '.'.join(parts)
			return result
		except (AttributeError):  # Not ready yet
			return None

	@CachedProperty('_ntiid_provider', '_ntiid_specific_part')
	def NTIID(self):
		provider = self._ntiid_provider
		if provider and self._ntiid_specific_part:
			return ntiids.make_ntiid(date=ntiids.DATE,
									 provider=provider,
									 nttype=self._ntiid_type,
									 specific=self._ntiid_specific_part)

@component.adapter(ICourseInstance)
@interface.implementer(IGradeBook,
					   an_interfaces.IAttributeAnnotatable,
					   zmime_interfaces.IContentTypeAware)
class GradeBook(nti_containers.CheckingLastModifiedBTreeContainer,
				zcontained.Contained,
				_NTIIDMixin):

	mimeType = mime_type = MIME_BASE + u'.gradebook'
	_ntiid_type = NTIID_TYPE_GRADE_BOOK

	def getColumnForAssignmentId(self, assignmentId):
		# TODO: This could be indexed
		for part in self.values():
			entry = part.get_entry_by_assignment(assignmentId)
			if entry is not None:
				return entry
		return None

	get_entry_by_assignment = alias('getColumnForAssignmentId')

	def get_entry_by_ntiid(self, ntiid):
		result = None
		type_ = ntiids.get_type(ntiid)
		if type_ == NTIID_TYPE_GRADE_BOOK_ENTRY:
			specific = ntiids.get_specific(ntiid)
			part, entry = specific.split('.')[-2:]
			result = self.get(part, {}).get(entry)
		return result

_GradeBookFactory = an_factory(GradeBook, 'GradeBook')

@interface.implementer(IGradeBookEntry,
					   an_interfaces.IAttributeAnnotatable,
					   zmime_interfaces.IContentTypeAware)
class GradeBookEntry(SchemaConfigured,
					 nti_containers.CheckingLastModifiedBTreeContainer,
					 zcontained.Contained,
					 _NTIIDMixin):

	mimeType = mime_type = MIME_BASE + u'.gradebookentry'

	_ntiid_include_self_name = True
	_ntiid_type = NTIID_TYPE_GRADE_BOOK_ENTRY

	createDirectFieldProperties(IGradeBookEntry)

	Name = alias('__name__')

	ntiid = alias('NTIID')
	gradeScheme = alias('GradeScheme')

	assignmentId = alias('AssignmentId')

	def __init__(self, **kwargs):
		# SchemaConfigured is not cooperative
		nti_containers.CheckingLastModifiedBTreeContainer.__init__(self)
		SchemaConfigured.__init__(self, **kwargs)


	def __setstate__(self, state):
		super(GradeBookEntry, self).__setstate__(state)
		if '_SampleContainer__data' not in self.__dict__:
			self._SampleContainer__data = self._newContainerData()

	@property
	def Items(self):
		return dict(self)

	@property
	def DueDate(self):
		try:
			return component.getUtility(IQAssignment, name=self.assignmentId).available_for_submission_ending
		except LookupError:
			return None

	def __str__(self):
		return self.displayName

	__repr__ = make_repr()

	def __eq__(self, other):
		try:
			return self is other or (self.NTIID == other.NTIID)
		except AttributeError:
			return NotImplemented

	def __hash__(self):
		xhash = 47
		xhash ^= hash(self.NTIID)
		return xhash


@interface.implementer(IGradeBookPart,
					   an_interfaces.IAttributeAnnotatable,
					   zmime_interfaces.IContentTypeAware)
class GradeBookPart(SchemaConfigured,
					nti_containers.CheckingLastModifiedBTreeContainer,
					zcontained.Contained,
					_NTIIDMixin):

	mimeType = mime_type = MIME_BASE + u'.gradebookpart'

	_ntiid_include_self_name = True
	_ntiid_type = NTIID_TYPE_GRADE_BOOK_PART

	createDirectFieldProperties(IGradeBookPart)

	__name__ = alias('Name')

	entryFactory = GradeBookEntry

	def __init__(self, **kwargs):
		# SchemaConfigured is not cooperative
		nti_containers.CheckingLastModifiedBTreeContainer.__init__(self)
		SchemaConfigured.__init__(self, **kwargs)

	def validateAssignment(self, assignment):
		return True

	def get_entry_by_assignment(self, assignmentId):
		# TODO: This could be indexed
		for entry in self.values():
			if entry.assignmentId == assignmentId:
				return entry
		return None

	@property
	def Items(self):
		return dict(self)

	def __str__(self):
		return self.displayName

	__repr__ = make_repr()

from .grades import Grade

class NoSubmitGradeBookEntryGrade(Grade):
	__external_class_name__ = 'Grade'

class NoSubmitGradeBookEntry(GradeBookEntry):
	__external_class_name__ = 'GradeBookEntry'


from nti.dataserver.traversal import ContainerAdapterTraversable

class NoSubmitGradeBookEntryTraversable(ContainerAdapterTraversable):
	"""
	Entries that cannot be submitted by students auto-generate
	NoSubmitGradeBookGrade objects (that they own but do not contain)
	when directly traversed to during request processing.

	We do this at request traversal time, rather than as part of the
	the get/__getitem__ method of the class, to not break any of the container
	assumptions.
	"""

	def traverse(self, name, furtherPath):
		try:
			return super(NoSubmitGradeBookEntryTraversable,self).traverse(name, furtherPath)
		except KeyError:
			# Check first for items in the container and named adapters.
			# Only if that fails do we dummy up a grade,
			# and only then if there is a real user by that name.
			if not User.get_user(name):
				raise

			result = NoSubmitGradeBookEntryGrade()
			result.__parent__ = self.context
			result.__name__ = name
			return result

class NoSubmitGradeBookPart(GradeBookPart):
	"""
	A special part of the gradebook for those things that
	cannot be submitted by students, only entered by the
	instructor.

	We use a special entry; see :class:`.NoSubmitGradeBookEntry`
	for details.
	"""

	__external_class_name__ = 'GradeBookPart'

	entryFactory = NoSubmitGradeBookEntry

	def validateAssignment(self, assignment):
		if assignment.category_name != NO_SUBMIT_PART_NAME:
			raise ValueError(assignment.category_name)
		if len(assignment.parts) != 0:
			raise ValueError("Too many parts")
		return True

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory

@interface.implementer(ISubmittedAssignmentHistory)
@component.adapter(IGradeBookEntry)
class _DefaultGradeBookEntrySubmittedAssignmentHistory(zcontained.Contained):

	__name__ = 'SubmittedAssignmentHistory'

	def __init__(self, entry, request=None):
		self.context = self.__parent__ = entry

	def __conform__(self, iface):
		if ICourseInstance.isOrExtends(iface):
			return find_interface(self, ICourseInstance)

	def __iter__(self):
		column = self.__parent__
		course = ICourseInstance(self)
		for username_that_submitted in column:
			user = User.get_user(username_that_submitted)
			if not user:
				continue
			history = component.getMultiAdapter( (course, user),
												 IUsersCourseAssignmentHistory)
			item = history[column.AssignmentId]

			yield (username_that_submitted, item)
