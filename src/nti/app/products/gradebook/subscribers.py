#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
.. $Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import lifecycleevent

from zope.annotation.interfaces import IAnnotations

from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectRemovedEvent
from zope.lifecycleevent.interfaces import IObjectModifiedEvent

from pyramid.traversal import find_interface

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItem

from nti.app.products.courseware.interfaces import ICourseInstanceAvailableEvent

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver import users
from nti.dataserver.activitystream_change import Change
from nti.dataserver import interfaces as nti_interfaces
from nti.dataserver.containers import CaseInsensitiveLastModifiedBTreeContainer

from . import assignments

from .grades import Grade
from .interfaces import IGrade
from .interfaces import IGradeBook
from .interfaces import IPendingAssessmentAutoGradePolicy

def find_gradebook_in_lineage(obj):
	book = find_interface(obj, IGradeBook)
	if book is None:
		__traceback_info__ = obj
		raise TypeError("Unable to find gradebook")
	return book

@component.adapter(IGrade, IObjectModifiedEvent)
def _grade_modified(grade, event):
	course = ICourseInstance(grade)
	user = users.User.get_user(grade.username)
	book = IGradeBook(course)
	entry = book.get_entry_by_ntiid(grade.ntiid)
	if user and entry is not None and entry.AssignmentId:
		assignment_history = component.getMultiAdapter( (course, user),
													    IUsersCourseAssignmentHistory)
		if entry.AssignmentId in assignment_history:
			item = assignment_history[entry.assignmentId]
			lifecycleevent.modified(item)

def _find_entry_for_item(item):
	assignmentId = item.Submission.assignmentId
	course = ICourseInstance(item, None)
	if course is None:
		# Typically during tests
		logger.warning("Assignment %s has no course", assignmentId)
		return None

	book = IGradeBook(course)

	entry = book.getColumnForAssignmentId(assignmentId)
	if entry is None:
		# Typically during tests something is added
		_synchronize_gradebook_with_course_instance(course,None)
		entry = book.getColumnForAssignmentId(assignmentId)
	if entry is None:
		# Also typically during tests.
		# TODO: Fix those tests to properly register assignments
		# so this branch goes away
		logger.warning("Assignment %s not found in course %s", assignmentId, course)
		return

	return entry

def _find_autograde_policy_for_course(course):
	registry = component

	# Courses may be ISites (couldn't we do this with
	# the context argument?)
	try:
		registry = course.getSiteManager()
		name = ''
		# If it is, we want the default utility in this course
	except LookupError:
		# If it isn't we need a named utility
		# This only works for the legacy courses
		name = course.ContentPackageNTIID

	return registry.queryUtility(IPendingAssessmentAutoGradePolicy, name=name)

@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectAddedEvent)
def _assignment_history_item_added(item, event):
	entry = _find_entry_for_item(item)
	if entry is not None:
		user = nti_interfaces.IUser(item)
		grade = Grade()

		# If there is an auto-grading policy for the course instance,
		# then let it convert the auto-assessed part of the submission
		# into the initial grade value
		course = ICourseInstance(item)
		policy = _find_autograde_policy_for_course(course)
		if policy is not None:
			grade.AutoGrade = policy.autograde(item.pendingAssessment)
			if grade.value is None:
				grade.value = grade.AutoGrade

		# Finally after we finish filling it in, publish it
		entry[user.username] = grade

@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectRemovedEvent)
def _assignment_history_item_removed(item, event):
	entry = _find_entry_for_item(item)
	if entry is not None:
		user = nti_interfaces.IUser(item)
		try:
			del entry[user.username]
		except KeyError:
			# Hmm...
			pass

@component.adapter(ICourseInstance, ICourseInstanceAvailableEvent)
def _synchronize_gradebook_with_course_instance(course, event):
	assignments.synchronize_gradebook(course)

###
# Storing notable items.
# We keep a parallel datastructure holding persistent objects
# that get indexed. It's updated based on events on grades, which
# fire when they are added or removed
###

_CHANGE_KEY = 'nti.app.products.gradebook.subscribers.ENTRY_CHANGE_KEY'

def _get_entry_change_storage(entry):
	annotes = IAnnotations(entry)
	changes = annotes.get(_CHANGE_KEY)
	if changes is None:
		changes = CaseInsensitiveLastModifiedBTreeContainer()
		changes.__name__ = _CHANGE_KEY
		changes.__parent__ = entry
		annotes[_CHANGE_KEY] = changes
	return annotes[_CHANGE_KEY]

from zope.securitypolicy.interfaces import IPrincipalRoleMap
from zope.securitypolicy.interfaces import Allow
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR


def _do_store_grade_created_event(grade, event):
	storage = _get_entry_change_storage(grade.__parent__)
	if grade.Username in storage:
		storage[grade.Username].updateLastMod()
		return

	change = Change(Change.CREATED, grade)

	# Copy the date info from the grade (primarily relevant
	# for migration); the change doesn't do this itself
	change.lastModified = grade.lastModified
	change.createdTime = grade.createdTime

	if grade.creator is not None:
		change.creator = grade.creator
	else:
		# If we can get to a course, we arbitrarily assume
		# it's from the first instructor in the list
		try:
			instance = ICourseInstance(grade)
			roles = IPrincipalRoleMap(instance)
			for instructor in instance.instructors:
				if roles.getSetting(RID_INSTRUCTOR, instructor.id) is Allow:
					change.creator = grade.creator = nti_interfaces.IUser(instructor)
					break
		except (TypeError,IndexError,AttributeError):
			pass

	# Give the change a sharedWith value of the target
	# username; that way it gets indexed cheaply as directed
	# to the user.
	# NOTE: See __acl__ on the grade object; this
	# may change if we have a richer publishing workflow
	change.sharedWith = (grade.Username,)
	change.__copy_object_acl__ = True

	# Now store it, firing events to index, etc. Remember this
	# only happens if the name and parent aren't already
	# set (which they will be because they were copied from
	# grade)
	del change.__name__
	del change.__parent__
	# Define it as top-level content for indexing purposes
	change.__is_toplevel_content__ = True
	storage[grade.Username] = change
	assert change.__parent__ is _get_entry_change_storage(grade.__parent__)
	assert change.__name__ == grade.Username
	return change

def _store_grade_created_event(grade, event):
	# We're registered for both added and modified events,
	# and we only store a change when the grade actually
	# gets a value for the first time.
	if grade.value is not None:
		_do_store_grade_created_event(grade, event)

@component.adapter(IGrade, IObjectRemovedEvent)
def _remove_grade_created_event(grade, event):
	try:
		del _get_entry_change_storage(grade.__parent__)[grade.Username]
	except KeyError:
		# hmm...
		pass
