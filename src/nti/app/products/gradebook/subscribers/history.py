#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectRemovedEvent
from zope.lifecycleevent.interfaces import IObjectModifiedEvent

from nti.app.assessment.interfaces import IObjectRegradeEvent
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItem

from nti.app.assessment.common.history import get_most_recent_history_item

from nti.app.products.gradebook.autograde_policies import find_autograde_policy

from nti.app.products.gradebook.interfaces import IGrade

from nti.app.products.gradebook.utils.gradebook import find_entry_for_item
from nti.app.products.gradebook.utils.gradebook import remove_grade_from_entry
from nti.app.products.gradebook.utils.gradebook import set_grade_by_assignment_history_item

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.users import User

logger = __import__('logging').getLogger(__name__)


@component.adapter(IGrade, IObjectModifiedEvent)
def _grade_modified(grade, unused_event=None):
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
    history_item = get_most_recent_history_item(user, course, entry.assignmentId)
    # TODO: What do we do here? Be nice to have deterministic
    # grade -> history_item.
    history_item.updateLastModIfGreater(grade.lastModified)


@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectAddedEvent)
def _assignment_history_item_added(item, unused_event=None):
    set_grade_by_assignment_history_item(item)


@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectModifiedEvent)
def _assignment_history_item_modified(item, unused_event=None):
    set_grade_by_assignment_history_item(item)


@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectRemovedEvent)
def _assignment_history_item_removed(item, unused_event=None):
    entry = find_entry_for_item(item)
    if entry is not None:
        user = IUser(item, None)
        if user is not None:
            try:
                remove_grade_from_entry(entry, user.username)
            except KeyError:
                pass


@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectRegradeEvent)
def _regrade_assignment_history_item(item, unused_event=None):
    assignmentId = item.assignmentId
    course = ICourseInstance(item, None)
    policy = find_autograde_policy(course, assignmentId)
    if policy is not None:
        set_grade_by_assignment_history_item(item)
