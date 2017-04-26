#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import time

from zope import component

from zope.annotation.interfaces import IAnnotations

from zope.catalog.interfaces import ICatalog

from zope.component.hooks import getSite

from zope.event import notify

from zope.intid.interfaces import IIntIds
from zope.intid.interfaces import IIntIdRemovedEvent

from zope.lifecycleevent import ObjectModifiedEvent
from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectRemovedEvent
from zope.lifecycleevent.interfaces import IObjectModifiedEvent

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap

from pyramid import httpexceptions as hexc

from pyramid.threadlocal import get_current_request

from pyramid.traversal import find_interface

from nti.app.assessment.interfaces import IObjectRegradeEvent
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItem

from nti.app.externalization.error import raise_json_error

from nti.app.products.gradebook import MessageFactory as _

from nti.app.products.gradebook import get_grade_catalog

from nti.app.products.gradebook.assignments import create_assignment_entry

from nti.app.products.gradebook.autograde_policies import find_autograde_policy_for_assignment_in_course

from nti.app.products.gradebook.index import IX_SITE
from nti.app.products.gradebook.index import IX_COURSE
from nti.app.products.gradebook.index import IX_STUDENT
from nti.app.products.gradebook.index import CATALOG_NAME

from nti.app.products.gradebook.interfaces import IGrade
from nti.app.products.gradebook.interfaces import IGradeBook

from nti.app.products.gradebook.utils import remove_from_container

from nti.app.products.gradebook.utils.gradebook import find_entry_for_item
from nti.app.products.gradebook.utils.gradebook import set_grade_by_assignment_history_item
from nti.app.products.gradebook.utils.gradebook import synchronize_gradebook_and_verify_policy

from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQEditableEvaluation

from nti.containers.containers import CaseInsensitiveLastModifiedBTreeContainer

from nti.contenttypes.courses import get_enrollment_catalog

from nti.contenttypes.courses.index import IX_USERNAME

from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceImportedEvent
from nti.contenttypes.courses.interfaces import ICourseInstanceAvailableEvent

from nti.dataserver.activitystream_change import Change

from nti.dataserver.interfaces import IUser

from nti.dataserver.users import User

from nti.dataserver.users.interfaces import IWillDeleteEntityEvent

from nti.publishing.interfaces import IObjectPublishedEvent
from nti.publishing.interfaces import IObjectUnpublishedEvent


def raise_error(v, tb=None, factory=hexc.HTTPUnprocessableEntity):
	request = get_current_request()
	raise_json_error(request, factory, v, tb)

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

	assignment_history = component.getMultiAdapter((course, user),
													IUsersCourseAssignmentHistory)
	if entry.AssignmentId in assignment_history:
		item = assignment_history[entry.assignmentId]
		item.updateLastModIfGreater(grade.lastModified)

@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectAddedEvent)
def _assignment_history_item_added(item, event):
	set_grade_by_assignment_history_item(item)

@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectModifiedEvent)
def _assignment_history_item_modified(item, event):
	set_grade_by_assignment_history_item(item)

@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectRegradeEvent)
def _regrade_assignment_history_item(item, event):
	assignmentId = item.assignmentId
	course = ICourseInstance(item, None)
	policy = find_autograde_policy_for_assignment_in_course(course, assignmentId)
	if policy is not None:
		set_grade_by_assignment_history_item(item)

@component.adapter(IQEditableEvaluation, IObjectPublishedEvent)
def _create_gradebook_entry_on_publish(item, event):
	if IQAssignment.providedBy(item):
		course = ICourseInstance(item, None)
		book = IGradeBook(course, None)
		if book is not None:
			displayName = item.title or 'Assignment'
			create_assignment_entry(course, item, displayName, _book=book)

@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectRemovedEvent)
def _assignment_history_item_removed(item, event):
	entry = find_entry_for_item(item)
	if entry is not None:
		user = IUser(item, None)
		if user is not None:
			try:
				remove_from_container(entry, user.username)
			except KeyError:
				# Hmm...
				pass

@component.adapter(IQEditableEvaluation, IObjectUnpublishedEvent)
def _on_evalulation_unpublished(item, event):
	if IQAssignment.providedBy(item):
		course = ICourseInstance(item, None)
		book = IGradeBook(course, None)
		if book is not None:
			entry = book.getColumnForAssignmentId(item.ntiid)
			if entry:
				raise_error(
					{
						u'message': _("Cannot unpublish assignment with grades."),
						u'code': 'CannotUnpublishObject',
					})

@component.adapter(ICourseInstance, ICourseInstanceAvailableEvent)
def _synchronize_gradebook_with_course_instance(course, event):
	synchronize_gradebook_and_verify_policy(course)

@component.adapter(ICourseInstance, ICourseInstanceImportedEvent)
def _on_course_instance_imported(course, event):
	synchronize_gradebook_and_verify_policy(course)

# Storing notable items.
# We keep a parallel datastructure holding persistent objects
# that get indexed. It's updated based on events on grades, which
# fire when they are added or removed

_CHANGE_KEY = 'nti.app.products.gradebook.subscribers.ENTRY_CHANGE_KEY'

def _get_user(user):
	if not IUser.providedBy(user) and user:
		result = User.get_user(str(user))
	else:
		result = user
	return user if result is None else user

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
		change_event = storage[grade.Username]
		change_event.updateLastMod()
		notify(ObjectModifiedEvent(change_event))
		return

	change = Change(Change.CREATED, grade)

	# Set the time to now. Since grades are created
	# at assignment submission time, we rely on the
	# change times for more accurate reporting.
	now = time.time()
	change.lastModified = now
	change.createdTime = now

	if grade.creator is not None:
		change.creator = _get_user(grade.creator)
	else:
		# If we can get to a course, we arbitrarily assume
		# it's from the first instructor in the list
		try:
			instance = ICourseInstance(grade)
			roles = IPrincipalRoleMap(instance)
			for instructor in instance.instructors:
				if roles.getSetting(RID_INSTRUCTOR, instructor.id) is Allow:
					grade.creator = instructor.id
					change.creator = IUser(instructor)
					break
		except (TypeError, IndexError, AttributeError):
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
	# set (which they will be because they were copied from grade)
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
		storage = _get_entry_change_storage(grade.__parent__)
		del storage[grade.Username]
	except KeyError:
		# hmm...
		pass

def unindex_grade_data(username):
	result = 0
	catalog = component.queryUtility(ICatalog, name=CATALOG_NAME)
	if catalog is not None:
		index = catalog[IX_STUDENT]
		# normalize
		if isinstance(username, bytes):
			username = username.decode('utf-8')
		username = username.lower().strip()
		# get all doc ids (it's a wrapper)
		values_to_documents = index.index.values_to_documents
		docs = values_to_documents.get(username) or ()
		for uid in tuple(docs):
			catalog.unindex_doc(uid)
			result += 1
	return result

def delete_user_data(user):
	username = user.username
	catalog = get_enrollment_catalog()
	intids = component.getUtility(IIntIds)
	query = { IX_USERNAME: {'any_of':(username,)} }
	for uid in catalog.apply(query) or ():
		context = intids.queryObject(uid)
		course = ICourseInstance(context, None)
		book = IGradeBook(course, None)
		if book is not None:
			book.remove_user(username)

@component.adapter(IUser, IWillDeleteEntityEvent)
def _on_user_will_be_removed(user, event):
	logger.info("Removing gradebook data for user %s", user)
	unindex_grade_data(user.username)
	delete_user_data(user=user)

# courses

def unindex_course_data(course):
	entry = ICourseCatalogEntry(course, None)
	if entry is not None:
		catalog = get_grade_catalog()
		query = { IX_COURSE: {'any_of':(entry.ntiid,)},
				  IX_SITE: {'any_of':(getSite().__name__,) } }
		for uid in catalog.apply(query) or ():
			catalog.unindex_doc(uid)

@component.adapter(ICourseInstance, IIntIdRemovedEvent)
def _on_course_instance_removed(course, event):
	unindex_course_data(course)
