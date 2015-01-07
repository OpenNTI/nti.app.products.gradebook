#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Grade book definition

.. $Id$
"""

from __future__ import unicode_literals, print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.annotation import factory as an_factory
from zope.annotation.interfaces import IAttributeAnnotatable

from zope.container.contained import Contained

from zope.mimetype.interfaces import IContentTypeAware

from pyramid.traversal import lineage

from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQAssignmentDateContext

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.users import User
from nti.dataserver.traversal import find_interface
from nti.dataserver.containers import CheckingLastModifiedBTreeContainer

from nti.externalization.representation import WithRepr

from nti.mimetype.mimetype import MIME_BASE

from nti.ntiids import ntiids

from nti.utils.property import alias
from nti.utils.property import CachedProperty

from nti.schema.schema import EqHash
from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import createDirectFieldProperties

from .interfaces import IGradeBook
from .interfaces import IGradeBookPart
from .interfaces import IGradeBookEntry
from .interfaces import NO_SUBMIT_PART_NAME
from .interfaces import NTIID_TYPE_GRADE_BOOK
from .interfaces import NTIID_TYPE_GRADE_BOOK_PART
from .interfaces import NTIID_TYPE_GRADE_BOOK_ENTRY
from .interfaces import ISubmittedAssignmentHistory
from .interfaces import ISubmittedAssignmentHistorySummaries

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
				parts.append(ntiids.make_specific_safe(location.__name__))
				if ICourseInstance.providedBy(location):
					break
			parts.reverse()
			result = None
			if None not in parts:
				result = '.'.join(parts)
			return result
		except AttributeError:  # Not ready yet
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
					   IAttributeAnnotatable,
					   IContentTypeAware)
class GradeBook(CheckingLastModifiedBTreeContainer,
				Contained,
				_NTIIDMixin):

	mimeType = mime_type = MIME_BASE + u'.gradebook'
	_ntiid_type = NTIID_TYPE_GRADE_BOOK

	def getColumnForAssignmentId(self, assignmentId, check_name=False):
		for part in self.values():
			entry = part.get_entry_by_assignment(assignmentId, check_name=check_name)
			if entry is not None:
				return entry
		return None
	get_entry_by_assignment = getEntryByAssignment = getColumnForAssignmentId

	def getEntryByNTIID(self, ntiid):
		result = None
		type_ = ntiids.get_type(ntiid)
		if type_ == NTIID_TYPE_GRADE_BOOK_ENTRY:
			specific = ntiids.get_specific(ntiid)
			part, entry = specific.split('.')[-2:]
			result = self.get(part, {}).get(entry)
		return result
	get_entry_by_ntiid = getEntryByNTIID
	
	def removeUser(self, username):
		result = 0
		for part in self.values():
			if part.removeUser(username):
				result +=1
		return result
	remove_user = removeUser
	
	@property
	def Items(self):
		return dict(self)
	
	def iter_grades(self, username):
		for part in self.values():
			for grade in part.iter_grades(username):
				yield grade

_GradeBookFactory= an_factory(GradeBook, 'GradeBook')

@interface.implementer(IGradeBookEntry,
					   IAttributeAnnotatable,
					   IContentTypeAware)
@WithRepr
@EqHash('NTIID',)
class GradeBookEntry(SchemaConfigured,
					 # XXX: FIXME: This is wrong, this should be a Case/INSENSITIVE/ btree,
					 # usernames are case insensitive. Everyone that uses this this
					 # has to be aware and can't do the usual thing of lower-casing for their
					 # own comparisons. Until we do a database migration we partially
					 # ameliorate this for __contains__ (at the cost of a performance penalty),
					 # but we can't completely
					 CheckingLastModifiedBTreeContainer,
					 Contained,
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
		CheckingLastModifiedBTreeContainer.__init__(self)
		SchemaConfigured.__init__(self, **kwargs)

	def __setstate__(self, state):
		super(GradeBookEntry, self).__setstate__(state)
		if '_SampleContainer__data' not in self.__dict__:
			self._SampleContainer__data = self._newContainerData()

	@property
	def _gbe_len(self):
		return len(self)

	@CachedProperty('_gbe_len')
	def _lower_keys_to_upper_key(self):
		# Caching based on the length isn't exactly correct, as an add
		# followed by a delete will be missed. However, we don't have a pattern
		# that does that, and it's much cheaper than calculating a set of the usernames
		return {k.lower():k for k in self.keys()}

	def __contains__(self, key):
		result = super(GradeBookEntry,self).__contains__(key)
		if not result and key and isinstance(key, basestring):
			# Sigh, long expensive path
			result = key.lower() in self._lower_keys_to_upper_key
		return result
	has_key = __contains__

	def __getitem__(self, key):
		try:
			return super(GradeBookEntry,self).__getitem__(key)
		except KeyError:
			if not key or not isinstance(key, basestring):
				raise

			# Sigh, long expensive path
			upper = self._lower_keys_to_upper_key.get(key.lower())
			if upper and upper != key: # careful not to infinite recurse
				return self.__getitem__(upper)
			raise

	def get(self, key, default=None):
		try:
			return self.__getitem__(key)
		except KeyError:
			return default

	@property
	def Items(self):
		return dict(self)

	@property
	def DueDate(self):
		try:
			asg =component.getUtility(IQAssignment, name=self.assignmentId)
			course = ICourseInstance(self)
			datecontext = IQAssignmentDateContext(course)
			return datecontext.of(asg).available_for_submission_ending
		except (LookupError,TypeError):
			return None

	def __str__(self):
		return self.displayName

@interface.implementer(IGradeBookPart,
					   IAttributeAnnotatable,
					   IContentTypeAware)
@WithRepr
class GradeBookPart(SchemaConfigured,
					CheckingLastModifiedBTreeContainer,
					Contained,
					_NTIIDMixin):

	mimeType = mime_type = MIME_BASE + u'.gradebookpart'

	_ntiid_include_self_name = True
	_ntiid_type = NTIID_TYPE_GRADE_BOOK_PART

	createDirectFieldProperties(IGradeBookPart)

	__name__ = alias('Name')

	entryFactory = GradeBookEntry

	def __init__(self, **kwargs):
		# SchemaConfigured is not cooperative
		CheckingLastModifiedBTreeContainer.__init__(self)
		SchemaConfigured.__init__(self, **kwargs)

	def validateAssignment(self, assignment):
		return True

	def getEntryByAssignment(self, assignmentId, check_name=False):
		for entry in self.values():
			if 	entry.assignmentId == assignmentId or \
				(check_name and entry.__name__ == assignmentId):
				return entry
		return None
	get_entry_by_assignment = getEntryByAssignment
	
	def removeUser(self, username):
		result = 0
		username = username.lower()
		for entry in self.values():
			if username in entry:
				del entry[username]
				result += 1
		return result
	remove_user = removeUser
	
	@property
	def Items(self):
		return dict(self)

	def iter_grades(self, username):
		for entry in self.values():
			if username in entry:
				yield entry[username]

	def __str__(self):
		return self.displayName

from .grades import Grade
from .grades import PersistentGrade

class GradeWithoutSubmission(Grade):
	"""
	A dummy grade we temporarily create before
	a submission comes in. These are never persistent.
	"""
	__external_class_name__ = 'Grade'
	__external_can_create__ = False

	def __reduce__(self):
		raise TypeError('Temporary grade only')
	__reduce_ex__ = __reduce__

NoSubmitGradeBookEntryGrade = GradeWithoutSubmission

class PersistentGradeWithoutSubmission(GradeWithoutSubmission, PersistentGrade):
	pass

PersistentNoSubmitGradeBookEntryGrade = PersistentGradeWithoutSubmission

class GradeBookEntryWithoutSubmission(GradeBookEntry):
	"""
	An entry in the gradebook that doesn't necessarily require
	students to already have a submission.
	"""
	__external_class_name__ = 'GradeBookEntry'
	__external_can_create__ = False

NoSubmitGradeBookEntry = GradeBookEntryWithoutSubmission

from nti.contenttypes.courses.interfaces import ICourseEnrollments

from nti.dataserver.traversal import ContainerAdapterTraversable

class GradeBookEntryWithoutSubmissionTraversable(ContainerAdapterTraversable):
	"""
	Entries that cannot be submitted by students auto-generate
	:class:`.GradeWithoutSubmission` objects (that they own but do not contain)
	when directly traversed to during request processing.

	We do this at request traversal time, rather than as part of the
	the get/__getitem__ method of the class, to not break any of the container
	assumptions.

	In general, prefer to register this only for special named parts; it is dangerous
	as a main traversal mechanism because of the possibility of blocking
	student submissions and the wide-ranging consequences of interfering
	with traversal.
	"""

	def traverse(self, name, furtherPath):
		try:
			return super(GradeBookEntryWithoutSubmissionTraversable,self).traverse(name, furtherPath)
		except KeyError:
			# Check first for items in the container and named adapters.
			# Only if that fails do we dummy up a grade,
			# and only then if there is a real user by that name
			# who is enrolled in this course.
			user = User.get_user(name)
			if not user:
				raise
			course = ICourseInstance(self.context)
			course_enrollments = ICourseEnrollments(course)
			if course_enrollments.get_enrollment_for_principal(user):
				result = GradeWithoutSubmission()
				result.__parent__ = self.context
				result.__name__ = name
				return result
			raise

class NoSubmitGradeBookPart(GradeBookPart):
	"""
	A special part of the gradebook for those things that
	cannot be submitted by students, only entered by the
	instructor. These assignments are validated as such.

	We use a special entry; see :class:`.NoSubmitGradeBookEntry`
	for details.
	"""

	__external_class_name__ = 'GradeBookPart'

	entryFactory = GradeBookEntryWithoutSubmission

	def validateAssignment(self, assignment):
		if assignment.category_name != NO_SUBMIT_PART_NAME:
			raise ValueError(assignment.category_name)
		if len(assignment.parts) != 0:
			raise ValueError("Too many parts")
		return True

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItemSummary

# By directly using this API and (not the adapter interface) and
# setting create to False, in a large course with many users but few
# submissions, we gain a significant performance improvement if we
# iterate across the entire list: 9 or 10x (This is because
# creating---and then discarding when we abort the GET request
# transaction---all those histories is expensive, requesting new OIDs
# from the database and firing lots of events). I'm not formalizing
# this API yet because we shouldn't be iterating across and
# materializing the entire list; if we can make that stop we won't
# need this.
# from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory
from nti.app.assessment.adapters import _histories_for_course
from nti.app.assessment.adapters import _history_for_user_in_course

_NotGiven = object()

@interface.implementer(ISubmittedAssignmentHistory)
@component.adapter(IGradeBookEntry)
class _DefaultGradeBookEntrySubmittedAssignmentHistory(Contained):

	__name__ = 'SubmittedAssignmentHistory'

	# We don't externalize this item, but we do create links to it,
	# and they want a mimeType
	mimeType = 'application/json'
	as_summary = False

	def __init__(self, entry, request=None):
		self.context = self.__parent__ = entry

	def __conform__(self, iface):
		if ICourseInstance.isOrExtends(iface):
			return find_interface(self, ICourseInstance)
		if IGradeBookEntry.isOrExtends(iface):
			return self.context

	@property
	def lastModified(self):
		"""
		Our last modified time is the time the column was modified
		by addition/removal of a grade.
		"""
		return self.context.lastModified

	def __bool__(self):
		return True
	__nonzero__ = __bool__

	def __len__(self):
		"""
		Getting the length of this object is extremely slow and should
		be avoided.

		The length is defined as the number of people that have submitted
		to the assignment; this is distinct from the number of grades that may
		exist, and much more expensive to compute.
		"""

		column = self.context
		assignment_id = column.AssignmentId
		course = ICourseInstance(self)
		histories = _histories_for_course(course)

		count = 0
		for history in histories.values():
			if assignment_id in history:
				count += 1
		return count

	def __iter__(self,
				 usernames=_NotGiven,
				 placeholder=_NotGiven,
				 forced_placeholder_usernames=None):
		column = self.context
		course = ICourseInstance(self)
		assignment_id = column.AssignmentId
		if usernames is _NotGiven:
			usernames = column
		if not forced_placeholder_usernames:
			forced_placeholder_usernames = ()

		# ensure we have a set (for speed) that we can be case-insensitive on
		# (for correctness)
		forced_placeholder_usernames = {x.lower() for x in forced_placeholder_usernames}

		for username_that_submitted in usernames:
			username_that_submitted = username_that_submitted.lower()

			if username_that_submitted in forced_placeholder_usernames:
				yield (username_that_submitted, placeholder)
				continue

			user = User.get_user(username_that_submitted)
			if not user:
				continue
			username_that_submitted = user.username # go back to canonical
			history = _history_for_user_in_course(course, user, create=False)

			try:
				item = history[assignment_id]
				if self.as_summary:
					item = IUsersCourseAssignmentHistoryItemSummary(item)
			except (KeyError,TypeError):
				if placeholder is not _NotGiven:
					yield (username_that_submitted, placeholder)
				else:
					# Hopefully only seen during migration;
					# in production this is an issue
					logger.exception("Mismatch between recorded submission and history submission for %s",
									 username_that_submitted)
			else:
				yield (username_that_submitted, item)

	def items(self,
			  usernames=_NotGiven,
			  placeholder=_NotGiven,
			  forced_placeholder_usernames=None):
		"""
		Return an iterator over the items (username, historyitem)
		that make up this object. This is just like iterating over
		this object normally, except the option of filtering.

		:keyword usernames: If given, an iterable of usernames.
			Only usernames that are in this iterable are returned.
			Furthermore, the items are returned in the same order
			as the usernames in the iterable. Note that if the username
			doesn't exist, nothing is returned for that entry
			unless `placeholder` is also provided.
		:keyword placeholder: If given (even if given as None)
			then all users in `usernames` will be returned; those
			that have not submitted will be returned with this placeholder
			value. This only makes sense if usernames is given.
		:keyword forced_placeholder_usernames: If given and not None, a container of usernames
			that define a subset of `usernames` that will return the
			placeholder, even if they did have a submission. Obviously
			this only makes sense if a placeholder is defined. This can make
			iteration faster if you know that only some subset of the usernames
			will actually be looked at (e.g., a particular numerical range).
		"""

		if placeholder is not _NotGiven and usernames is _NotGiven:
			raise ValueError("Placeholder only makes sense if usernames is given")

		if forced_placeholder_usernames is not None and placeholder is _NotGiven:
			raise ValueError("Ignoring users only works with a ploceholder")

		return self.__iter__(usernames=usernames,
							 placeholder=placeholder,
							 forced_placeholder_usernames=forced_placeholder_usernames)

	def __getitem__(self, username):
		"""
		We are traversable to users
		"""
		(username, item), = self.items(usernames=(username,), placeholder=None)
		if item is not None:
			return item
		raise KeyError(username)

@interface.implementer(ISubmittedAssignmentHistorySummaries)
@component.adapter(IGradeBookEntry)
class _DefaultGradeBookEntrySubmittedAssignmentHistorySummaries(_DefaultGradeBookEntrySubmittedAssignmentHistory):
	__name__ = 'SubmittedAssignmentHistorySummaries'
	as_summary = True
