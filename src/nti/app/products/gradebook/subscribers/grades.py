#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import time

from zope import component
from zope import interface

from zope.annotation.interfaces import IAnnotations

from zope.event import notify

from zope.lifecycleevent import ObjectModifiedEvent

from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectRemovedEvent
from zope.lifecycleevent.interfaces import IObjectModifiedEvent

from zope.security.management import queryInteraction

from nti.app.products.gradebook.interfaces import IGrade
from nti.app.products.gradebook.interfaces import IGradeRemovedEvent
from nti.app.products.gradebook.interfaces import IGradeChangeContainer

from nti.containers.containers import CaseInsensitiveLastModifiedBTreeContainer

from nti.contenttypes.completion.interfaces import UserProgressRemovedEvent

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.coremetadata.interfaces import SYSTEM_USER_NAME

from nti.dataserver.activitystream_change import Change

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.users import User

from nti.ntiids.ntiids import find_object_with_ntiid

_CHANGE_KEY = 'nti.app.products.gradebook.subscribers.ENTRY_CHANGE_KEY'

logger = __import__('logging').getLogger(__name__)


def _get_user(user):
    if not IUser.providedBy(user) and user:
        result = User.get_user(user)
    else:
        result = user
    return user if result is None else user


def _get_entry_change_storage(entry):
    annotes = IAnnotations(entry)
    changes = annotes.get(_CHANGE_KEY)
    if changes is None:
        changes = CaseInsensitiveLastModifiedBTreeContainer()
        interface.alsoProvides(changes, IGradeChangeContainer)
        changes.__name__ = _CHANGE_KEY
        changes.__parent__ = entry
        annotes[_CHANGE_KEY] = changes
    return annotes[_CHANGE_KEY]


def _do_store_grade_created_event(grade, _):
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
        change.creator = _get_user(grade.creator) if grade.creator != SYSTEM_USER_NAME else SYSTEM_USER_NAME
    else:
        change.creator = SYSTEM_USER_NAME
        grade.creator = SYSTEM_USER_NAME

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


@component.adapter(IGrade, IObjectAddedEvent)
@component.adapter(IGrade, IObjectModifiedEvent)
def _store_grade_created_event(grade, event):
    # We're registered for both added and modified events,
    # and we only store a change when the grade actually
    # gets a value for the first time.
    if grade.value is not None:
        _do_store_grade_created_event(grade, event)


@component.adapter(IGrade, IObjectRemovedEvent)
def _remove_grade_event(grade, unused_event=None):
    try:
        storage = _get_entry_change_storage(grade.__parent__)
        del storage[grade.Username]
    except KeyError:
        pass


@component.adapter(IGrade, IObjectAddedEvent)
@component.adapter(IGrade, IObjectModifiedEvent)
def update_grade_progress(grade, unused_event=None):
    if queryInteraction() is None:
        return
    user = IUser(grade, None)
    # Tests
    if user is None:
        return
    assignment = find_object_with_ntiid(grade.AssignmentId)
    course = ICourseInstance(grade)
    # Do the removed event since we want to recalculate progress
    # after this step.
    notify(UserProgressRemovedEvent(assignment,
                                    user,
                                    course))


@component.adapter(IGrade, IGradeRemovedEvent)
def _on_grade_removed(unused_grade, event):
    # Specific event because we want item out of container at this point
    if queryInteraction() is None:
        return
    # Tests
    if event.user is None:
        return
    assignment = find_object_with_ntiid(event.assignment_ntiid)
    notify(UserProgressRemovedEvent(assignment,
                                    event.user,
                                    event.course))

