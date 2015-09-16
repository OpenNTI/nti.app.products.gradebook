#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
gradebook adapters

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItem

from nti.appserver.interfaces import ITrustedTopLevelContainerContextProvider

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver.users import User
from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IStreamChangeEvent

from nti.traversal.traversal import find_interface

from .grades import PersistentGrade

from .interfaces import IGrade
from .interfaces import IGradeBook
from .interfaces import IGradeBookEntry

@interface.implementer(IGradeBookEntry)
@component.adapter(IGrade)
def _GradeToGradeEntry(grade):
	return grade.__parent__

@interface.implementer(IGradeBookEntry)
@component.adapter(IUsersCourseAssignmentHistoryItem)
def _AssignmentHistoryItem2GradeBookEntry(item):
	assignmentId = item.__name__  # by definition
	course = ICourseInstance(item, None)
	# get gradebook entry definition
	gradebook = IGradeBook(course, None)
	if gradebook is not None:
		entry = gradebook.getColumnForAssignmentId(assignmentId)
		return entry

@interface.implementer(ICourseInstance)
def _as_course(context):
	"""
	Registered as an adapter for things we expect to be a descendant of a course
	"""
	return find_interface(context, ICourseInstance,
						  # Don't be strict so that we can still find it
						  # if some parent object has already had its
						  # __parent__ set to None, as during object removal
						  strict=False)

@interface.implementer(ICourseCatalogEntry)
def _as_catalog_entry(context):
	course = ICourseInstance(context, None)
	result = ICourseCatalogEntry(course, None)
	return result

def _no_pickle(*args):
	raise TypeError("This object cannot be pickled")

@interface.implementer(IGrade)
def grade_for_history_item(item):
	"""
	Registered as an adapter for both history item and summary
	"""
	course = ICourseInstance(item, None)
	if course is None:  # during tests
		return
	user = IUser(item)  # Can we do this with just the item? item.creator?
	book = IGradeBook(course)
	assignmentId = item.Submission.assignmentId
	entry = book.getColumnForAssignmentId(assignmentId)
	if entry is not None:
		grade = entry.get(user.username)
		if grade is None:
			# Always dummy up a grade (at the right location in
			# the hierarchy) so that we have an 'edit' link if
			# necessary
			grade = PersistentGrade()
			grade.createdTime = 0
			grade.lastModified = 0
			grade.__parent__ = entry
			grade.__name__ = user.username
		return grade
	return None

@interface.implementer(IUsersCourseAssignmentHistoryItem)
@component.adapter(IGrade)
def history_item_for_grade(grade):
	user = IUser(grade)
	course = ICourseInstance(grade)
	history = component.getMultiAdapter((course, user), IUsersCourseAssignmentHistory)
	assg_id = grade.__parent__.AssignmentId
	try:
		return history[assg_id]
	except KeyError:
		raise TypeError("No history for grade")

@interface.implementer(IUser)
@component.adapter(IGrade)
def grade_to_user(grade):
	return User.get_user(grade.__name__)

@interface.implementer(ITrustedTopLevelContainerContextProvider)
@component.adapter(IGrade)
def _trusted_context_from_grade(obj):
	course = _as_course( obj )
	results = ()
	if course is not None:
		catalog_entry = ICourseCatalogEntry( course, None )
		results = (catalog_entry,) if catalog_entry is not None else ()
	return results

@interface.implementer(ITrustedTopLevelContainerContextProvider)
@component.adapter(IStreamChangeEvent)
def _trusted_context_from_change(obj):
	obj = getattr( obj, 'object', None )
	return _trusted_context_from_grade(obj)
