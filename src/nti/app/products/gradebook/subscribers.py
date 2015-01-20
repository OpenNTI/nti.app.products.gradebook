#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from functools import partial

from zope import component
from zope.annotation.interfaces import IAnnotations

from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectRemovedEvent
from zope.lifecycleevent.interfaces import IObjectModifiedEvent

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap

from pyramid.traversal import find_interface

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItem

from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments
from nti.contenttypes.courses.interfaces import ICourseInstanceAvailableEvent

from nti.dataserver.interfaces import IUser

from nti.dataserver.users import User
from nti.dataserver.users.interfaces import IWillDeleteEntityEvent

from nti.dataserver.activitystream_change import Change

from nti.dataserver.containers import CaseInsensitiveLastModifiedBTreeContainer

from nti.site.hostpolicy import run_job_in_all_host_sites

from .grades import PersistentGrade

from .interfaces import IGrade
from .interfaces import IGradeBook

from .utils import save_in_container
from .utils import remove_from_container

from .assignments import synchronize_gradebook

from .grading import find_grading_policy_for_course

from .autograde_policies import find_autograde_policy_for_assignment_in_course

def find_gradebook_in_lineage(obj):
	book = find_interface(obj, IGradeBook)
	if book is None:
		__traceback_info__ = obj
		raise TypeError("Unable to find gradebook")
	return book

@component.adapter(IGrade, IObjectModifiedEvent)
def _grade_modified(grade, event):
	"""
	When a grade is modified, make sure that the history item that
	conceptually contains it is updated too.
	"""
	entry = grade.__parent__
	if entry is None or not entry.AssignmentId:
		# not yet
		return

	user = User.get_user(grade.username)
	if user is None:
		return

	course = ICourseInstance(grade, None)
	if course is None:
		# not yet
		return

	assignment_history = component.getMultiAdapter( (course, user),
												    IUsersCourseAssignmentHistory)
	if entry.AssignmentId in assignment_history:
		item = assignment_history[entry.assignmentId]
		item.updateLastModIfGreater(grade.lastModified)

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

@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectAddedEvent)
def _assignment_history_item_added(item, event):
	entry = _find_entry_for_item(item)
	if entry is not None:
		user = IUser(item)
		grade = PersistentGrade()
		grade.username = user.username
		
		# If there is an auto-grading policy for the course instance,
		# then let it convert the auto-assessed part of the submission
		# into the initial grade value
		course = ICourseInstance(item)
		assignmentId = item.Submission.assignmentId
		policy = find_autograde_policy_for_assignment_in_course(course, assignmentId)
		if policy is not None:
			autograde = policy.autograde(item.pendingAssessment)
			if autograde is not None:
				grade.AutoGrade, grade.AutoGradeMax = autograde
			if grade.value is None:
				grade.value = grade.AutoGrade
		# Finally after we finish filling it in, publish it
		save_in_container(entry, user.username, grade)
		
@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectRemovedEvent)
def _assignment_history_item_removed(item, event):
	entry = _find_entry_for_item(item)
	if entry is not None:
		user = IUser(item)
		try:
			remove_from_container(entry, user.username)
		except KeyError:
			# Hmm...
			pass

@component.adapter(ICourseInstance, ICourseInstanceAvailableEvent)
def _synchronize_gradebook_with_course_instance(course, event):
	synchronize_gradebook(course)
	## CS: We validate the grading policy to make sure 
	## the gradebook has been synchronized
	policy = find_grading_policy_for_course(course)
	if policy is not None:
		policy.validate()

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

def _do_store_grade_created_event(grade, event):
	storage = _get_entry_change_storage(grade.__parent__)
	if grade.Username in storage:
		storage[grade.Username].updateLastMod()
		return

	change = Change(Change.CREATED, grade)

	## Copy the date info from the grade (primarily relevant
	## for migration); the change doesn't do this itself
	change.lastModified = grade.lastModified
	change.createdTime = grade.createdTime

	if grade.creator is not None:
		change.creator = grade.creator
	else:
		## If we can get to a course, we arbitrarily assume
		## it's from the first instructor in the list
		try:
			instance = ICourseInstance(grade)
			roles = IPrincipalRoleMap(instance)
			for instructor in instance.instructors:
				if roles.getSetting(RID_INSTRUCTOR, instructor.id) is Allow:
					change.creator = grade.creator = IUser(instructor)
					break
		except (TypeError,IndexError,AttributeError):
			pass

	## Give the change a sharedWith value of the target
	## username; that way it gets indexed cheaply as directed
	## to the user.
	## NOTE: See __acl__ on the grade object; this
	## may change if we have a richer publishing workflow
	change.sharedWith = (grade.Username,)
	change.__copy_object_acl__ = True

	## Now store it, firing events to index, etc. Remember this
	## only happens if the name and parent aren't already
	## set (which they will be because they were copied from grade)
	del change.__name__
	del change.__parent__
	
	## Define it as top-level content for indexing purposes
	change.__is_toplevel_content__ = True
	storage[grade.Username] = change
	assert change.__parent__ is _get_entry_change_storage(grade.__parent__)
	assert change.__name__ == grade.Username
	return change

def _store_grade_created_event(grade, event):
	## We're registered for both added and modified events,
	## and we only store a change when the grade actually
	## gets a value for the first time.
	if grade.value is not None:
		_do_store_grade_created_event(grade, event)

@component.adapter(IGrade, IObjectRemovedEvent)
def _remove_grade_created_event(grade, event):
	try:
		storage = _get_entry_change_storage(grade.__parent__)
		del storage[grade.Username]
	except KeyError:
		# hmm...
		pass

def delete_user_data(user):
	username = user.username
	for enrollments in component.subscribers( (user,), IPrincipalEnrollments):
		for enrollment in enrollments.iter_enrollments():
			course = ICourseInstance(enrollment, None)
			book = IGradeBook(course, None)
			if book is not None:
				book.remove_user(username)

@component.adapter(IUser, IWillDeleteEntityEvent)
def _on_user_will_be_removed(user, event):
	logger.info("Removing gradebook data for user %s", user)
	func = partial(delete_user_data, user=user)
	run_job_in_all_host_sites(func)
